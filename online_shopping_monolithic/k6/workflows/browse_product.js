import http from "k6/http";
import { check } from "k6";
import { BASE_URL, PRODUCT_IDS } from "../utils/config.js";
import { getToken } from "../utils/multipleAuth.js";

// Run this ramping-vus version FIRST to (re)confirm the ceiling if you
// change anything below. Once confirmed, swap to the fixed_load block
// beneath it for the actual 70%-load experiment run.
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 70,           // 70 iterations/s × 4 requests ≈ 280 req/s (70% of ~401 req/s ceiling)
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 250,
        },
    },
};

// Real 70%-load config -- swap this in for the block above once confirmed.
//
// export const options = {
//     scenarios: {
//         fixed_load: {
//             executor: "constant-arrival-rate",
//             rate: 37,           // 37 iterations/s x 4 requests ~= 148 req/s (70% of ~209 req/s ceiling)
//             timeUnit: "1s",
//             duration: "2m",
//             preAllocatedVUs: 20,
//             maxVUs: 60,
//         },
//     },
// };

function getProductForVU() {
    const index = (__VU - 1) % PRODUCT_IDS.length;
    return PRODUCT_IDS[index];
}

function getSecondProductForVU() {
    // Pick a different product than getProductForVU() so the "get multiple
    // products" call always requests two distinct, real IDs.
    const index = __VU % PRODUCT_IDS.length;
    return PRODUCT_IDS[index];
}

export default function () {
    const token = getToken();
    const productId = getProductForVU();
    const secondProductId = getSecondProductForVU();

    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    // 1. Get all products
    const resProducts = http.get(`${BASE_URL}/`, params);
    check(resProducts, {
        "get all products succeeded": (r) => r.status === 200,
    });

    // 2. Get products by category
    const resCategory = http.get(`${BASE_URL}/category/Electronics`, params);
    check(resCategory, {
        "get products by category succeeded": (r) => r.status === 200,
    });

    // 3. Get product details
    const resDetails = http.get(`${BASE_URL}/${productId}`, params);
    check(resDetails, {
        "get product details succeeded": (r) => r.status === 200,
    });

    // 4. Get multiple products
    const payload = JSON.stringify({
        ids: [productId, secondProductId]
    });
    const resMultiple = http.post(`${BASE_URL}/ids`, payload, params);
    check(resMultiple, {
        "get multiple products succeeded": (r) => r.status === 200,
    });
}