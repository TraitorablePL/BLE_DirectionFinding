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
#include <sys/byteorder.h>
#include <sys/printk.h>
#include <sys/util.h>
#include <zephyr.h>
#include <zephyr/types.h>

// Switching Pattern (2us sample - 2us switching - 2us sample - 2us switching)

// Length of CTE in unit of 8[us]
#define CTE_LEN (0x04U)  // 18 samples in 1us switching
//#define CTE_LEN (0x02U)  // 9 samples

static void adv_sent_cb(struct bt_le_ext_adv *adv,
                        struct bt_le_ext_adv_sent_info *info);

const static struct bt_le_ext_adv_cb adv_callbacks = {
    .sent = adv_sent_cb,
};

static struct bt_le_ext_adv *adv_set;

const static struct bt_le_adv_param param = BT_LE_ADV_PARAM_INIT(
    BT_LE_ADV_OPT_EXT_ADV | BT_LE_ADV_OPT_USE_NAME, BT_GAP_ADV_FAST_INT_MIN_2,
    BT_GAP_ADV_FAST_INT_MAX_2, NULL);

static struct bt_le_ext_adv_start_param ext_adv_start_param = {
    .timeout = 0,
    .num_events = 0,
};

const static struct bt_le_per_adv_param per_adv_param = {
    .interval_min = BT_GAP_ADV_SLOW_INT_MIN,
    .interval_max = BT_GAP_ADV_SLOW_INT_MAX,
    .options = BT_LE_ADV_OPT_USE_TX_POWER,
};

const struct bt_df_adv_cte_tx_param cte_params = {
    .cte_len = CTE_LEN,
    .cte_count = 1,
    .cte_type = BT_DF_CTE_TYPE_AOA,
    .num_ant_ids = 0,
    .ant_ids = NULL};

static void adv_sent_cb(struct bt_le_ext_adv *adv,
                        struct bt_le_ext_adv_sent_info *info) {
    printk("Advertiser[%d] %p sent %d\n", bt_le_ext_adv_get_index(adv), adv,
           info->num_sent);
}

void main(void) {
    char addr_s[BT_ADDR_LE_STR_LEN];
    struct bt_le_oob oob_local;
    int err;

    /* Initialize the Bluetooth Subsystem */
    printk("Bluetooth initialization...");
    err = bt_enable(NULL);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success\n");

    printk("Advertising set create...");
    err = bt_le_ext_adv_create(&param, &adv_callbacks, &adv_set);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success\n");

    printk("Update CTE params...");
    err = bt_df_set_adv_cte_tx_param(adv_set, &cte_params);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success\n");

    printk("Periodic advertising params set...");
    err = bt_le_per_adv_set_param(adv_set, &per_adv_param);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success\n");

    printk("Enable CTE...");
    err = bt_df_adv_cte_tx_enable(adv_set);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success\n");

    printk("Periodic advertising enable...");
    err = bt_le_per_adv_start(adv_set);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success\n");

    printk("Extended advertising enable...");
    err = bt_le_ext_adv_start(adv_set, &ext_adv_start_param);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success\n");

    bt_le_ext_adv_oob_get_local(adv_set, &oob_local);
    bt_addr_le_to_str(&oob_local.addr, addr_s, sizeof(addr_s));

    printk("Started extended advertising as %s\n", addr_s);
}
