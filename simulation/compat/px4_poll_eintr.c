/*
 * PX4 v1.15.x exits its daemon poll loop on EINTR and unlinks the command
 * socket. amd64 execution on Apple Silicon reproduces that during startup.
 * Retry only infinite waits on PX4's command-server socket. Preserve normal
 * poll/fortify behavior, timeouts and signal handling for all other callers.
 * Remove this workaround once the shipped PX4 handles EINTR in server.cpp.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <poll.h>
#include <stddef.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>

static int is_px4_server(const struct pollfd *fds, nfds_t count)
{
    if (count == 0 || fds == NULL || fds[0].fd < 0) {
        return 0;
    }
    struct sockaddr_un address = {0};
    socklen_t length = sizeof(address);
    const char prefix[] = "/tmp/px4-sock-";
    return getsockname(fds[0].fd, (struct sockaddr *)&address, &length) == 0
        && address.sun_family == AF_UNIX
        && length >= offsetof(struct sockaddr_un, sun_path) + sizeof(prefix)
        && memcmp(address.sun_path, prefix, sizeof(prefix) - 1) == 0;
}

int poll(struct pollfd *fds, nfds_t count, int timeout)
{
    int (*original)(struct pollfd *, nfds_t, int) = dlsym(RTLD_NEXT, "poll");
    if (original == NULL) {
        errno = ENOSYS;
        return -1;
    }
    for (;;) {
        int result = original(fds, count, timeout);
        int error = errno;
        if (result >= 0 || error != EINTR || timeout >= 0 || !is_px4_server(fds, count)) {
            errno = error;
            return result;
        }
    }
}

/* The published PX4 binary uses glibc's fortified entry point. */
int __poll_chk(struct pollfd *fds, nfds_t count, int timeout, size_t size)
{
    int (*original)(struct pollfd *, nfds_t, int, size_t) = dlsym(RTLD_NEXT, "__poll_chk");
    if (original == NULL) {
        errno = ENOSYS;
        return -1;
    }
    for (;;) {
        int result = original(fds, count, timeout, size);
        int error = errno;
        if (result >= 0 || error != EINTR || timeout >= 0 || !is_px4_server(fds, count)) {
            errno = error;
            return result;
        }
    }
}
