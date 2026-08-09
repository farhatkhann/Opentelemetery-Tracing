import http from "k6/http";
import { check } from "k6";
import { BASE_URL, PRODUCT_IDS, QUANTITY } from "../utils/config.js";
import { getToken } from "../utils/multipleAuth.js";

export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 34,              // ~70% of measured ~230-256 req/s ceiling
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 20,
            maxVUs: 300,
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

    // 1. Get Products
    const browseRes = http.get(`${BASE_URL}/`, params);
    check(browseRes, {
        "browse products succeeded": (r) => r.status === 200,
    });

    // 2. Add Product to Cart
    // NOTE: the /cart route destructures `_id` and `qty` from req.body
    // (see products.js), not `productId` -- sending the wrong key means
    // _id arrives as undefined, which crashes the server (see chat history).
    const cartPayload = JSON.stringify({
        _id: productId,
        qty: QUANTITY
    });
    const addRes = http.put(`${BASE_URL}/cart`, cartPayload, params);
    check(addRes, {
        "add to cart succeeded": (r) => r.status === 200 || r.status === 201,
    });

    // 3. View Cart
    const viewRes = http.get(`${BASE_URL}/shopping/cart`, params);
    check(viewRes, {
        "view cart succeeded": (r) => r.status === 200,
    });

    // 4. Update Cart
    const updatePayload = JSON.stringify({
        _id: productId,
        qty: QUANTITY + 1
    });
    const updateRes = http.put(`${BASE_URL}/cart`, updatePayload, params);
    check(updateRes, {
        "update cart succeeded": (r) => r.status === 200,
    });

    // 5. Delete Cart Item
    const delRes = http.del(`${BASE_URL}/cart/${productId}`, null, params);
    check(delRes, {
        "delete cart item succeeded": (r) => r.status === 200 || r.status === 204,
    });
}