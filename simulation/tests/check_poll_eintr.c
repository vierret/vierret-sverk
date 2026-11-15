/* Real signals/socket readiness: ensure the workaround only retries PX4 waits. */
#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

extern int __poll_chk(struct pollfd *, nfds_t, int, size_t);
static pthread_t waiting_thread;
static struct sockaddr_un address;

static void on_signal(int number) { (void)number; }

static void *interrupt_then_connect(void *unused)
{
    (void)unused;
    usleep(30000);
    assert(pthread_kill(waiting_thread, SIGUSR1) == 0);
    usleep(30000);
    int client = socket(AF_UNIX, SOCK_STREAM, 0);
    assert(client >= 0);
    assert(connect(client, (struct sockaddr *)&address, sizeof(address)) == 0);
    close(client);
    return NULL;
}

static void check(const char *path, int timeout, int fortified, int retry)
{
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
    snprintf(address.sun_path, sizeof(address.sun_path), "%s", path);
    unlink(path);
    int server = socket(AF_UNIX, SOCK_STREAM, 0);
    assert(server >= 0);
    assert(bind(server, (struct sockaddr *)&address, sizeof(address)) == 0);
    assert(listen(server, 1) == 0);
    waiting_thread = pthread_self();
    pthread_t sender;
    assert(pthread_create(&sender, NULL, interrupt_then_connect, NULL) == 0);
    struct pollfd fd = {.fd = server, .events = POLLIN};
    int result = fortified ? __poll_chk(&fd, 1, timeout, sizeof(fd)) : poll(&fd, 1, timeout);
    int error = errno;
    if (retry) {
        assert(result == 1 && (fd.revents & POLLIN));
    } else {
        assert(result == -1 && error == EINTR);
    }
    assert(pthread_join(sender, NULL) == 0);
    close(server);
    unlink(path);
}

int main(void)
{
    struct sigaction handler = {.sa_handler = on_signal};
    sigemptyset(&handler.sa_mask);
    assert(sigaction(SIGUSR1, &handler, NULL) == 0);
    for (int fortified = 0; fortified <= 1; ++fortified) {
        check("/tmp/px4-sock-regression", -1, fortified, 1);
        check("/tmp/other-sock-regression", -1, fortified, 0);
        check("/tmp/px4-sock-regression", 500, fortified, 0);
    }
    puts("PASS: poll and __poll_chk retry only infinite PX4-server waits");
    return 0;
}
