/*
 * Copyright (c) 2022 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <bluetooth/bluetooth.h>
#include <bluetooth/conn.h>
#include <bluetooth/direction.h>
#include <bluetooth/gatt.h>
#include <bluetooth/hci.h>
#include <bluetooth/uuid.h>
#include <drivers/uart.h>
#include <errno.h>
#include <stddef.h>
#include <sys/byteorder.h>
#include <sys/printk.h>
#include <sys/reboot.h>
#include <zephyr.h>
#include <zephyr/types.h>

// Increased latency, to give time for PDU reception on receiver side
#define CONN_LATENCY 0U

// Arbitrary selected timeout value
#define CONN_TIMEOUT 1000U

// Interval used to run CTE request procedure periodically.
// Value is a number of connection events.
#define CTE_REQ_INTERVAL (CONN_LATENCY + 10U)

// Length of CTE in unit of 8 us
#define CTE_LEN (0x14U)

#define PATTERN_LIMIT 30

#define DF_FEAT_ENABLED BIT64(BT_LE_FEAT_BIT_CONN_CTE_RESP)

static void phy_update(struct bt_conn *conn,
                       const struct bt_conn_le_phy_param *param) {
    int err;
    err = bt_conn_le_phy_update(conn, param);

    printk("Update connection PHY params...");

    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success.\n");
}

static struct bt_conn *default_conn;
static const struct bt_le_conn_param conn_params =
    BT_LE_CONN_PARAM_INIT(BT_GAP_INIT_CONN_INT_MIN, BT_GAP_INIT_CONN_INT_MAX,
                          CONN_LATENCY, CONN_TIMEOUT);

// Antenna patterns for ISP AoA Demo Kit
// ANT_1    -> 0x5
// ANT_2    -> 0x6
// ANT_3    -> 0x4
// ANT_4    -> 0x9
// ANT_5    -> 0xA
// ANT_6    -> 0x8
// ANT_7    -> 0xD
// ANT_8    -> 0xE
// ANT_9    -> 0xC
// ANT_10   -> 0x1
// ANT_11   -> 0x2
// ANT_12   -> 0x0
// GND      -> 0x3, 0x7, 0xB, 0xF

// Simple horizontal
// static const uint8_t ant_patterns[] = {0x2, 0x2, 0x0, 0x5, 0x6,
//                                        0xA, 0x8, 0xD, 0xE};

// Simple vertical
static const uint8_t ant_patterns[] = {0x6, 0x6, 0x4, 0x9, 0xA, 0xE, 0xC, 0x1, 0x2};

// Complex
// static const uint8_t ant_patterns[] = {0x2, 0x2, 0x0, 0x5, 0x6, 0x4, 0x9,
// 0xA, 0x8, 0xD, 0xE, 0xC, 0x1};

// Complex with corner calibration
// static const uint8_t ant_patterns[] = {0x2, 0x2, 0x0, 0x5, 0x6, 0x6, 0x4,
// 0x9, 0xA, 0xA, 0x8, 0xD, 0xE, 0xE, 0xC, 0x1, 0x2};

static void start_scan(void);

///////////////////////////////////
//// Convert to string functions
///////////////////////////////////

static const char *phy2str(uint8_t phy) {
    switch (phy) {
        case 0:
            return "No packets";
        case BT_GAP_LE_PHY_1M:
            return "LE 1M";
        case BT_GAP_LE_PHY_2M:
            return "LE 2M";
        case BT_GAP_LE_PHY_CODED:
            return "LE Coded";
        default:
            return "Unknown";
    }
}

static const char *ant_pattern2str() {
    static char str[PATTERN_LIMIT];
    int i;
    for (i = 0; i < ARRAY_SIZE(ant_patterns) && i < PATTERN_LIMIT; i++) {
        if (ant_patterns[i] < 0xA) {
            str[i] = '0' + ant_patterns[i];
        } else if (ant_patterns[i] < 0x10) {
            str[i] = 'A' + (ant_patterns[i] - 0xA);
        } else {
            str[i] = 'X';
        }
    }
    str[i + 1] = '\0';
    return str;
}

static const char *cte_type2str(uint8_t type) {
    switch (type) {
        case BT_DF_CTE_TYPE_AOA:
            return "AOA";
        case BT_DF_CTE_TYPE_AOD_1US:
            return "AOD 1 [us]";
        case BT_DF_CTE_TYPE_AOD_2US:
            return "AOD 2 [us]";
        default:
            return "Unknown";
    }
}

static const char *packet_status2str(uint8_t status) {
    switch (status) {
        case BT_DF_CTE_CRC_OK:
            return "CRC OK";
        case BT_DF_CTE_CRC_ERR_CTE_BASED_TIME:
            return "CRC not OK, CTE Info OK";
        case BT_DF_CTE_CRC_ERR_CTE_BASED_OTHER:
            return "CRC not OK, Sampled other way";
        case BT_DF_CTE_INSUFFICIENT_RESOURCES:
            return "No resources";
        default:
            return "Unknown";
    }
}
///////////////////////////////////
//// UART
///////////////////////////////////

#define UART_DEVICE_NODE DT_CHOSEN(zephyr_shell_uart)
#define MSG_SIZE 32

static const struct device *uart_dev = DEVICE_DT_GET(UART_DEVICE_NODE);

static char rx_buf[MSG_SIZE];
static int rx_buf_pos;

static void perform_command(char *cmd) {
    if (strcmp(cmd, "reset") == 0) {
        sys_reboot(SYS_REBOOT_COLD);
    }
    // else if (strcmp(cmd, "1") == 0 && default_conn != NULL) {
    //     // TODO: Crashes MCU! To try with delayed routine
    //     printk("Activate 1M PHY\n");
    //     phy_update(default_conn, BT_CONN_LE_PHY_PARAM_1M);
    // } else if (strcmp(cmd, "2") == 0 && default_conn != NULL) {
    //     printk("Activate 2M PHY\n");
    //     // TODO: Crashes MCU! To try with delayed routine
    //     phy_update(default_conn, BT_CONN_LE_PHY_PARAM_2M);
    else {
    }
}

static void uart_rx_cb(const struct device *dev, void *user_data) {
    uint8_t c;

    if (!uart_irq_update(uart_dev)) {
        return;
    }

    while (uart_irq_rx_ready(uart_dev)) {
        uart_fifo_read(uart_dev, &c, 1);

        if ((c == '\n' || c == '\r') && rx_buf_pos > 0) {
            rx_buf[rx_buf_pos] = '\0';
            perform_command(rx_buf);
            rx_buf_pos = 0;
        } else if (rx_buf_pos < (sizeof(rx_buf) - 1)) {
            rx_buf[rx_buf_pos++] = c;
        }
    }
}

static bool eir_found(struct bt_data *data, void *user_data) {
    bt_addr_le_t *addr = user_data;
    uint64_t u64 = 0U;
    int err;

    // printk("[AD]: %u data_len %u\n", data->type, data->data_len);

    switch (data->type) {
        case BT_DATA_LE_SUPPORTED_FEATURES:
            if (data->data_len > sizeof(u64)) {
                return true;
            }

            (void)memcpy(&u64, data->data, data->data_len);

            u64 = sys_le64_to_cpu(u64);

            if (!(u64 & DF_FEAT_ENABLED)) {
                return true;
            }

            err = bt_le_scan_stop();
            if (err) {
                printk("Stop LE scan failed (err %d)\n", err);
                return true;
            }

            err = bt_conn_le_create(addr, BT_CONN_LE_CREATE_CONN, &conn_params,
                                    &default_conn);
            if (err) {
                printk("Create conn failed (err %d)\n", err);
                start_scan();
            }
            return false;
    }

    return true;
}

static void device_found(const bt_addr_le_t *addr, int8_t rssi, uint8_t type,
                         struct net_buf_simple *ad) {
    char dev[BT_ADDR_LE_STR_LEN];

    bt_addr_le_to_str(addr, dev, sizeof(dev));
    printk("[DEVICE]: %s, AD evt type %u, AD data len %u, RSSI %i\n", dev, type,
           ad->len, rssi);

    // We're only interested in connectable events
    if (type == BT_GAP_ADV_TYPE_ADV_IND ||
        type == BT_GAP_ADV_TYPE_ADV_DIRECT_IND) {
        bt_data_parse(ad, eir_found, (void *)addr);
    }
}

static void disable_cte_request(void) {
    int err;

    const struct bt_df_conn_cte_rx_param cte_rx_params = {
        .cte_types = BT_DF_CTE_TYPE_ALL,
        .slot_durations = 0x1,
        .num_ant_ids = ARRAY_SIZE(ant_patterns),
        .ant_ids = ant_patterns,
    };

    const struct bt_df_conn_cte_req_params cte_req_params = {
        .interval = CTE_REQ_INTERVAL,
        .cte_length = CTE_LEN,
        .cte_type = BT_DF_CTE_TYPE_AOA,
    };

    printk("Enable receiving of CTE...");
    err = bt_df_conn_cte_rx_enable(default_conn, &cte_rx_params);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success.");

    printk("Request CTE from peer device...");
    err = bt_df_conn_cte_req_enable(default_conn, &cte_req_params);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success.\n");
}

static void enable_cte_request(void) {
    int err;

    const struct bt_df_conn_cte_rx_param cte_rx_params = {
        .cte_types = BT_DF_CTE_TYPE_ALL,
        .slot_durations = 0x1,
        .num_ant_ids = ARRAY_SIZE(ant_patterns),
        .ant_ids = ant_patterns,
    };

    const struct bt_df_conn_cte_req_params cte_req_params = {
        .interval = CTE_REQ_INTERVAL,
        .cte_length = CTE_LEN,
        .cte_type = BT_DF_CTE_TYPE_AOA,
    };

    printk("Enable receiving of CTE...");
    err = bt_df_conn_cte_rx_enable(default_conn, &cte_rx_params);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success.");

    printk("Request CTE from peer device...");
    err = bt_df_conn_cte_req_enable(default_conn, &cte_req_params);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success.\n");
}

static void start_scan(void) {
    int err;

    // Use active scanning and disable duplicate filtering to handle any
    // devices that might update their advertising data at runtime.
    struct bt_le_scan_param scan_param = {
        .type = BT_LE_SCAN_TYPE_ACTIVE,
        .options = BT_LE_SCAN_OPT_NONE,
        .interval = BT_GAP_SCAN_FAST_INTERVAL,
        .window = BT_GAP_SCAN_FAST_WINDOW,
    };

    err = bt_le_scan_start(&scan_param, device_found);
    if (err) {
        printk("Scanning failed to start (err %d)\n", err);
        return;
    }

    printk("Scanning successfully started\n");
}

static void connected(struct bt_conn *conn, uint8_t conn_err) {
    char addr[BT_ADDR_LE_STR_LEN];
    int interval = 10;

    bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));

    if (conn_err) {
        printk("Failed to connect to %s (%u)\n", addr, conn_err);

        bt_conn_unref(default_conn);
        default_conn = NULL;

        start_scan();
        return;
    }

    printk("${\"Addr\":\"%s\"}\n", addr);
    // printk("${\"Addr\":\"%s\",\"Interval\":\"%ums\",\"PHY\":\"%s\"}\n", le_addr,
    //        , phy2str(info->phy));

    phy_update(default_conn, BT_CONN_LE_PHY_PARAM_1M);
    // phy_update(default_conn, BT_CONN_LE_PHY_PARAM_2M);

    if (conn == default_conn) {
        enable_cte_request();
    }
}

static void disconnected(struct bt_conn *conn, uint8_t reason) {
    char addr[BT_ADDR_LE_STR_LEN];

    bt_addr_le_to_str(bt_conn_get_dst(conn), addr, sizeof(addr));

    printk("Disconnected: %s (reason 0x%02x)\n", addr, reason);

    if (default_conn != conn) {
        return;
    }

    bt_conn_unref(default_conn);
    default_conn = NULL;

    start_scan();
}

static void cte_recv_cb(struct bt_conn *conn,
                        struct bt_df_conn_iq_samples_report const *report) {
    printk(
        "${\"Pattern\":\"%s\",\"Channel\":%d,\"PHY\":\"%s\",\"Samples\":%d,"
        "\"Slot\":\"%uus\","
        "\"RSSI\":%i,\"IQ\":[",
        ant_pattern2str(), report->chan_idx, phy2str(report->rx_phy),
        report->sample_count, report->slot_durations, report->rssi);

    struct bt_hci_le_iq_sample *samp = report->sample;
    for (uint8_t i = 0; i < report->sample_count; i++) {
        if (i == report->sample_count - 1)
            printk("[%d,%d]]}\n", samp[i].i, samp[i].q);
        else
            printk("[%d,%d],", samp[i].i, samp[i].q);
    }
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
    .connected = connected,
    .disconnected = disconnected,
    .cte_report_cb = cte_recv_cb,
};

void main(void) {
    int err;

    if (!device_is_ready(uart_dev)) {
        printk("UART device not found!");
        return;
    }

    // configure interrupt and callback to receive data
    uart_irq_callback_user_data_set(uart_dev, uart_rx_cb, NULL);
    uart_irq_rx_enable(uart_dev);

    err = bt_enable(NULL);
    if (err) {
        printk("Bluetooth init failed (err %d)\n", err);
        return;
    }

    printk("Bluetooth initialized\n");
    printk("Init device tracking\n");

    start_scan();
}
