// Run via `px4-dyn`: exercise the real HRT callback/re-arm race without flying.
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <thread>

extern "C" {
struct hrt_call {
    hrt_call *next;
    uint64_t deadline;
    uint64_t period;
    void (*callout)(void *);
    void *arg;
};
uint64_t hrt_absolute_time();
void hrt_call_every(hrt_call *, uint64_t, uint64_t, void (*)(void *), void *);
void hrt_cancel(hrt_call *);
}

static hrt_call target{}, heartbeat{};
static std::atomic<int> calls{0}, beats{0};
static void count(void *) { ++beats; }
static void callback(void *)
{
    if (++calls == 1) {
        // Let another thread re-arm this very entry while it is being invoked.
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

extern "C" int px4_module_main(int, char **)
{
    hrt_call_every(&heartbeat, 1000, 10000, count, nullptr);
    hrt_call_every(&target, 1000, 20000, callback, nullptr);
    std::thread rearm([] {
        while (calls.load() == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        hrt_call_every(&target, 20000, 20000, callback, nullptr);
    });
    rearm.detach();
    std::this_thread::sleep_for(std::chrono::seconds(2));
    int result = beats.load() > 5 && calls.load() > 2 ? 0 : 1;
    FILE *report = std::fopen("/tmp/px4-hrt-rearm-result", "w");
    std::fprintf(report, "%s: HRT callback re-arm: heartbeat=%d callbacks=%d\n",
                result ? "FAIL" : "PASS", beats.load(), calls.load());
    std::fclose(report);
    // Keep storage alive until PX4 exits, even if its queue is already damaged.
    if (!result) {
        hrt_cancel(&target);
        hrt_cancel(&heartbeat);
    }
    return result;
}
