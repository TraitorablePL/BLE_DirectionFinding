#include <bluetooth/bluetooth.h>
#include <bluetooth/conn.h>
#include <bluetooth/direction.h>
#include <bluetooth/gatt.h>
#include <bluetooth/hci.h>
#include <bluetooth/uuid.h>
#include <errno.h>
#include <stddef.h>
#include <string.h>
#include <sys/byteorder.h>
#include <sys/printk.h>
#include <zephyr.h>
#include <zephyr/types.h>

#define DF_FEAT_ENABLED BIT64(BT_LE_FEAT_BIT_CONN_CTE_RESP)

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    BT_DATA_BYTES(BT_DATA_LE_SUPPORTED_FEATURES,
                  BT_LE_SUPP_FEAT_24_ENCODE(DF_FEAT_ENABLED)),
};

static void enable_cte_response(struct bt_conn *conn) {
    int err;

    const struct bt_df_conn_cte_tx_param cte_tx_params = {
        .cte_types = BT_DF_CTE_TYPE_AOA,
    };

    printk("Set CTE transmission params...");
    err = bt_df_set_conn_cte_tx_param(conn, &cte_tx_params);
    if (err) {
        printk("failed (err %d)\n", err);
        return;
    }
    printk("success.\n");

    printk("Set CTE response enable...");
    err = bt_df_conn_cte_rsp_enable(conn);
    if (err) {
        printk("failed (err %d).\n", err);
        return;
    }
    printk("success.\n");
}

static void connected(struct bt_conn *conn, uint8_t err) {
    if (err) {
        printk("Connection failed (err 0x%02x)\n", err);
    } else {
        printk("Connected\n");
    }
    enable_cte_response(conn);
}

static void disconnected(struct bt_conn *conn, uint8_t reason) {
    printk("Disconnected (reason 0x%02x)\n", reason);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
    .connected = connected,
    .disconnected = disconnected,
};

static void bt_ready(void) {
    int err;

    printk("Bluetooth initialized\n");

    err = bt_le_adv_start(BT_LE_ADV_CONN_NAME, ad, ARRAY_SIZE(ad), NULL, 0);
    if (err) {
        printk("Advertising failed to start (err %d)\n", err);
        return;
    }
    printk("Advertising started...");
}

void main(void) {
    int err;

    err = bt_enable(NULL);
    if (err) {
        printk("Bluetooth init failed (err %d)\n", err);
        return;
    }

    bt_ready();
}
