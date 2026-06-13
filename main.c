#include <stdio.h>
#include "pico/stdlib.h"

#define BTN_PIN       15
#define DEBOUNCE_US   4000
#define HEARTBEAT_US  1000000

int main() {
    stdio_init_all();

    gpio_init(BTN_PIN);
    gpio_set_dir(BTN_PIN, GPIO_IN);
    gpio_pull_up(BTN_PIN);

    int last_raw      = gpio_get(BTN_PIN);
    int stable_state  = last_raw;
    absolute_time_t last_edge_time = get_absolute_time();
    absolute_time_t last_beat_time = get_absolute_time();

    while (true) {
        int raw = gpio_get(BTN_PIN);

        if (raw != last_raw) {
            last_raw = raw;
            last_edge_time = get_absolute_time();
        }

        if (raw != stable_state &&
            absolute_time_diff_us(last_edge_time, get_absolute_time()) > DEBOUNCE_US) {
            stable_state = raw;
            if (stable_state == 0) {
                printf("P\n");
            } else {
                printf("R\n");
            }
        }

        if (absolute_time_diff_us(last_beat_time, get_absolute_time()) > HEARTBEAT_US) {
            last_beat_time = get_absolute_time();
            printf("H\n");
        }

        sleep_us(500);
    }
}
