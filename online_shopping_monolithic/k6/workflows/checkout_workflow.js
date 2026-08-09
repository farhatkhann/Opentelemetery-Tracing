import http from "k6/http";
import { check } from "k6";
import {
    BASE_URL,
    PRODUCT_IDS,
    QUANTITY,
    TAX_NUMBER
} from "../utils/config.js";
import { getToken } from "../utils/multipleAuth.js";

// Run this ramping-vus version FIRST to find this workflow's real ceiling
// (place-order likely has its own cost profile -- don't assume it matches
// wishlist/cart's ~230-260 req/s ceiling).
// export const options = {
//     scenarios: {
//         fixed_load: {
//             executor: "constant-arrival-rate",
//             rate: 23,              // ~70% of measured ~114 req/s ceiling
//             timeUnit: "1s",
//             duration: "2m",
//             preAllocatedVUs: 20,
//             maxVUs: 150,
//         },
//     },
// };

// Once you have the ceiling, swap the block above for this, with `rate`
// set to (0.70 * ceiling_req_per_sec) / 5, since this workflow makes
// 5 requests per iteration (browse, add-to-cart, view-cart, place-order,
// view-orders).
//
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 23,          // 23 iterations/s × 5 requests ≈ 115 req/s (70% of ~163 req/s ceiling)
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 15,
            maxVUs: 150,
        },
    },
};

function getProductForVU() {
    const index = (__VU - 1) % PRODUCT_IDS.length;
    return PRODUCT_IDS[index];
}

export default function () {
    const token = getToken();
    const productId = getProductForVU();

    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    // 1. Browse Products
    const browseRes = http.get(`${BASE_URL}/`, params);
    check(browseRes, {
        "browse products succeeded": (r) => r.status === 200,
    });

    // 2. Add Product to Cart
    // NOTE: the /cart route expects `_id`, not `productId` (see products.js).
    const cartPayload = JSON.stringify({
        _id: productId,
        qty: QUANTITY
    });
    const addRes = http.put(`${BASE_URL}/cart`, cartPayload, params);
    check(addRes, {
        "add to cart succeeded": (r) => r.status === 200 || r.status === 201,
    });

    // 3. View Cart
    const viewCartRes = http.get(`${BASE_URL}/shopping/cart`, params);
    check(viewCartRes, {
        "view cart succeeded": (r) => r.status === 200,
    });

    // 4. Place Order
    const orderPayload = JSON.stringify({
        txnNumber: TAX_NUMBER
    });
    const orderRes = http.post(`${BASE_URL}/shopping/order`, orderPayload, params);
    check(orderRes, {
        "place order succeeded": (r) => r.status === 200,
    });

    // 5. View Orders
    const ordersRes = http.get(`${BASE_URL}/shopping/orders`, params);
    check(ordersRes, {
        "view orders succeeded": (r) => r.status === 200,
    });
}