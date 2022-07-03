/*
 * Copyright (c) 2021 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

#include <bluetooth/bluetooth.h>
#include <bluetooth/direction.h>
#include <bluetooth/hci.h>
#include <errno.h>
#include <stddef.h>
#include <zephyr.h>

#define DEBUG_LOG 0
#define PATTERN_LIMIT 16

#define DEVICE_NAME CONFIG_BT_DEVICE_NAME
#define DEVICE_NAME_LEN (sizeof(DEVICE_NAME) - 1)
#define PEER_NAME_LEN_MAX 30
/* BT Core 5.3 specification allows controller to wait 6 periodic advertising
 * events for synchronization establishment, hence timeout must be longer than
 * that.
 */
#define SYNC_CREATE_TIMEOUT_INTERVAL_NUM 7
/* Maximum length of advertising data represented in hexadecimal format */
#define ADV_DATA_HEX_STR_LEN_MAX (BT_GAP_ADV_MAX_EXT_ADV_DATA_LEN * 2 + 1)

static struct bt_le_per_adv_sync *sync;
static bt_addr_le_t per_addr;
static volatile bool per_adv_found;
static bool scan_enabled;
static uint8_t per_sid;
static uint32_t sync_create_timeout_ms;

static K_SEM_DEFINE(sem_per_adv, 0, 1);
static K_SEM_DEFINE(sem_per_sync, 0, 1);
static K_SEM_DEFINE(sem_per_sync_lost, 0, 1);

/*
 * Antenna patterns for ISP AoA Demo Kit
 * ANT_1    -> 0x5
 * ANT_2    -> 0x6
 * ANT_3    -> 0x4
 * ANT_4    -> 0x9
 * ANT_5    -> 0xA
 * ANT_6    -> 0x8
 * ANT_7    -> 0xD
 * ANT_8    -> 0xE
 * ANT_9    -> 0xC
 * ANT_10   -> 0x1
 * ANT_11   -> 0x2
 * ANT_12   -> 0x0
 */

// static const uint8_t ant_pattern[] = {0x2, 0x0, 0x5, 0x6, 0x1, 0x4,
//                                        0xC, 0x9, 0xE, 0xD, 0x8, 0xA};

static const uint8_t ant_pattern[] = {0x2, 0x2, 0x0, 0x5, 0x6};

static inline uint32_t adv_interval_to_ms(uint16_t interval) {
    return interval * 5 / 4;
}

static const char *ant_pattern2str() {
    static char str[PATTERN_LIMIT];
    int i;
    for (i = 0; i < ARRAY_SIZE(ant_pattern) && i < PATTERN_LIMIT; i++) {
        if (ant_pattern[i] < 0xA) {
            str[i] = '0' + ant_pattern[i];
        } else if (ant_pattern[i] < 0x10) {
            str[i] = 'A' + ant_pattern[i];
        } else {
            str[i] = 'X';
        }
    }
    str[i + 1] = '\0';
    return str;
}

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

static const char *cte_type2str(uint8_t type) {
    switch (type) {
        case BT_DF_CTE_TYPE_AOA:
            return "AOA";
        case BT_DF_CTE_TYPE_AOD_1US:
            return "AOD 1 [us]";
        case BT_DF_CTE_TYPE_AOD_2US:
            return "AOD 2 [us]";
        case BT_DF_CTE_TYPE_NONE:
            return "";
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

static bool data_cb(struct bt_data *data, void *user_data) {
    char *name = user_data;
    uint8_t len;

    switch (data->type) {
        case BT_DATA_NAME_SHORTENED:
        case BT_DATA_NAME_COMPLETE:
            len = MIN(data->data_len, PEER_NAME_LEN_MAX - 1);
            memcpy(name, data->data, len);
            name[len] = '\0';
            return false;
        default:
            return true;
    }
}

static void sync_cb(struct bt_le_per_adv_sync *sync,
                    struct bt_le_per_adv_sync_synced_info *info) {
#if DEBUG_LOG
    char le_addr[BT_ADDR_LE_STR_LEN];
    bt_addr_le_to_str(info->addr, le_addr, sizeof(le_addr));
    printk(
        "PER_ADV_SYNC[%u]: [DEVICE]: %s synced, "
        "Interval 0x%04x (%u ms), PHY %s\n",
        bt_le_per_adv_sync_get_index(sync), le_addr, info->interval,
        adv_interval_to_ms(info->interval), phy2str(info->phy));
#else
    printk("Interval: %u ms\n", adv_interval_to_ms(info->interval));
#endif
    k_sem_give(&sem_per_sync);
}

static void term_cb(struct bt_le_per_adv_sync *sync,
                    const struct bt_le_per_adv_sync_term_info *info) {
    char le_addr[BT_ADDR_LE_STR_LEN];

    bt_addr_le_to_str(info->addr, le_addr, sizeof(le_addr));

#if DEBUG_LOG
    printk("PER_ADV_SYNC[%u]: [DEVICE]: %s sync terminated\n",
           bt_le_per_adv_sync_get_index(sync), le_addr);
#else
    printk("Sync terminated\n");
#endif

    k_sem_give(&sem_per_sync_lost);
}

static void recv_cb(struct bt_le_per_adv_sync *sync,
                    const struct bt_le_per_adv_sync_recv_info *info,
                    struct net_buf_simple *buf) {
// Periodical advertising for AoA transmission
#if DEBUG_LOG
    static char data_str[ADV_DATA_HEX_STR_LEN_MAX];
    char le_addr[BT_ADDR_LE_STR_LEN];

    bt_addr_le_to_str(info->addr, le_addr, sizeof(le_addr));
    bin2hex(buf->data, buf->len, data_str, sizeof(data_str));

    printk(
        "PER_ADV_SYNC[%u]: [DEVICE]: %s, tx_power %i, "
        "RSSI %i, CTE %s, data length %u, data: %s\n",
        bt_le_per_adv_sync_get_index(sync), le_addr, info->tx_power, info->rssi,
        cte_type2str(info->cte_type), buf->len, data_str);
#endif
}

static void cte_recv_cb(
    struct bt_le_per_adv_sync *sync,
    struct bt_df_per_adv_sync_iq_samples_report const *report) {
#if DEBUG_LOG
    printk(
        "CTE: samples count %d, cte type %s, slot durations: %u [us], "
        "packet status %s, RSSI %i\n",
        bt_le_per_adv_sync_get_index(sync), report->sample_count,
        cte_type2str(report->cte_type), report->slot_durations,
        packet_status2str(report->packet_status), report->rssi);
#else
    printk(
        "Pattern: %s, samples: %d, slot: %u [us], status: %s, RSSI: %i,\nIQ:{",
        ant_pattern2str(), report->sample_count, report->slot_durations,
        packet_status2str(report->packet_status), report->rssi);
#endif

    struct bt_hci_le_iq_sample *samp = report->sample;
    for (uint8_t i = 0; i < report->sample_count; i++) {
#if DEBUG_LOG
        printk("Sample %d (I: %d, Q: %d)\n", i, samp[i].i, samp[i].q);
#else
        if (i == report->sample_count - 1)
            printk("(%d,%d)}\n\n", samp[i].i, samp[i].q);
        else
            printk("(%d,%d),", samp[i].i, samp[i].q);
#endif
    }
}

static struct bt_le_per_adv_sync_cb sync_callbacks = {
    .synced = sync_cb,
    .term = term_cb,
    .recv = recv_cb,
    .cte_report_cb = cte_recv_cb,
};

static void scan_recv(const struct bt_le_scan_recv_info *info,
                      struct net_buf_simple *buf) {
#if DEBUG_LOG
    char le_addr[BT_ADDR_LE_STR_LEN];
    char name[PEER_NAME_LEN_MAX];

    (void)memset(name, 0, sizeof(name));

    bt_data_parse(buf, data_cb, name);

    bt_addr_le_to_str(info->addr, le_addr, sizeof(le_addr));

    printk(
        "[DEVICE]: %s, AD evt type %u, Tx Pwr: %i, RSSI %i %s C:%u S:%u "
        "D:%u SR:%u E:%u Prim: %s, Secn: %s, Interval: 0x%04x (%u ms), "
        "SID: %u\n",
        le_addr, info->adv_type, info->tx_power, info->rssi, name,
        (info->adv_props & BT_GAP_ADV_PROP_CONNECTABLE) != 0,
        (info->adv_props & BT_GAP_ADV_PROP_SCANNABLE) != 0,
        (info->adv_props & BT_GAP_ADV_PROP_DIRECTED) != 0,
        (info->adv_props & BT_GAP_ADV_PROP_SCAN_RESPONSE) != 0,
        (info->adv_props & BT_GAP_ADV_PROP_EXT_ADV) != 0,
        phy2str(info->primary_phy), phy2str(info->secondary_phy),
        info->interval, adv_interval_to_ms(info->interval), info->sid);
#endif

    if (!per_adv_found && info->interval) {
        sync_create_timeout_ms = adv_interval_to_ms(info->interval) *
                                 SYNC_CREATE_TIMEOUT_INTERVAL_NUM;
        per_adv_found = true;
        per_sid = info->sid;
        bt_addr_le_copy(&per_addr, info->addr);

        k_sem_give(&sem_per_adv);
    }
}

static struct bt_le_scan_cb scan_callbacks = {
    .recv = scan_recv,
};

static void create_sync(void) {
    struct bt_le_per_adv_sync_param sync_create_param;
    int err;

#if DEBUG_LOG
    printk("Creating Periodic Advertising Sync...");
#endif
    bt_addr_le_copy(&sync_create_param.addr, &per_addr);
    sync_create_param.options = 0;
    sync_create_param.sid = per_sid;
    sync_create_param.skip = 0;
    sync_create_param.timeout = 0xa;
    err = bt_le_per_adv_sync_create(&sync_create_param, &sync);
    if (err) {
#if DEBUG_LOG
        printk("failed (err %d)\n", err);
#endif
        return;
    }
#if DEBUG_LOG
    printk("success.\n");
#endif
}

static int delete_sync(void) {
    int err;
#if DEBUG_LOG
    printk("Deleting Periodic Advertising Sync...");
#endif
    err = bt_le_per_adv_sync_delete(sync);
    if (err) {
#if DEBUG_LOG
        printk("failed (err %d)\n", err);
#endif
        return err;
    }
#if DEBUG_LOG
    printk("success\n");
#endif
    return 0;
}

static void enable_cte_rx(void) {
    int err;

    const struct bt_df_per_adv_sync_cte_rx_param cte_rx_params = {
        .max_cte_count = 5,
        .cte_types = BT_DF_CTE_TYPE_AOA,
        .slot_durations = 0x1,
        .num_ant_ids = ARRAY_SIZE(ant_pattern),
        .ant_ids = ant_pattern,
    };
#if DEBUG_LOG
    printk("Enable receiving of CTE...\n");
#endif
    err = bt_df_per_adv_sync_cte_rx_enable(sync, &cte_rx_params);
    if (err) {
#if DEBUG_LOG
        printk("failed (err %d)\n", err);
#endif
        return;
    }
#if DEBUG_LOG
    printk("success\n");
#endif
}

static int scan_init(void) {
    // printk("Scan callbacks register...");
    bt_le_scan_cb_register(&scan_callbacks);
    // printk("success.\n");

    // printk("Periodic Advertising callbacks register...");
    bt_le_per_adv_sync_cb_register(&sync_callbacks);
    // printk("success.\n");

    return 0;
}

static int scan_enable(void) {
    struct bt_le_scan_param param = {
        .type = BT_LE_SCAN_TYPE_ACTIVE,
        .options = BT_LE_SCAN_OPT_FILTER_DUPLICATE,
        .interval = BT_GAP_SCAN_FAST_INTERVAL,
        .window = BT_GAP_SCAN_FAST_WINDOW,
        .timeout = 0U,
    };

    int err;

    if (!scan_enabled) {
#if DEBUG_LOG
        printk("Start scanning...");
#endif
        err = bt_le_scan_start(&param, NULL);
        if (err) {
#if DEBUG_LOG
            printk("failed (err %d)\n", err);
#endif
            return err;
        }
#if DEBUG_LOG
        printk("success\n");
#endif
        scan_enabled = true;
    }

    return 0;
}

static void scan_disable(void) {
    int err;

#if DEBUG_LOG
    printk("Scan disable...");
#endif
    err = bt_le_scan_stop();
    if (err) {
#if DEBUG_LOG
        printk("failed (err %d)\n", err);
#endif
        return;
    }
#if DEBUG_LOG
    printk("Success.\n");
#endif
    scan_enabled = false;
}

void main(void) {
    int err = bt_enable(NULL);
#if DEBUG_LOG
    printk("Bluetooth initialization...");
    if (err) {
        printk("failed (err %d)\n", err);
    }
    printk("success\n");
#else
    printk("Init device tracking.\n");
#endif

    scan_init();

    scan_enabled = false;

    while (true) {
        per_adv_found = false;
        scan_enable();
#if DEBUG_LOG
        printk("Waiting for periodic advertising...\n");
#endif
        err = k_sem_take(&sem_per_adv, K_FOREVER);
        if (err) {
#if DEBUG_LOG
            printk("failed (err %d)\n", err);
#endif
            return;
        }
#if DEBUG_LOG
        printk("success. Found periodic advertising.\n");
#endif
        create_sync();

#if DEBUG_LOG
        printk("Waiting for periodic sync...\n");
#endif
        err = k_sem_take(&sem_per_sync, K_MSEC(sync_create_timeout_ms));
        if (err) {
#if DEBUG_LOG
            printk("failed (err %d)\n", err);
#endif
            err = delete_sync();
            if (err) {
                return;
            }
            continue;
        }
#if DEBUG_LOG
        printk("success. Periodic sync established.\n");
#endif

        enable_cte_rx();

        /* Disable scan to cleanup output */
        scan_disable();

#if DEBUG_LOG
        printk("Waiting for periodic sync lost...\n");
#endif
        err = k_sem_take(&sem_per_sync_lost, K_FOREVER);
        if (err) {
#if DEBUG_LOG
            printk("failed (err %d)\n", err);
#endif
            return;
        }
#if DEBUG_LOG
        printk("Periodic sync lost.\n");
#endif
    }
}
