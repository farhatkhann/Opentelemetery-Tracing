import http from "k6/http";
import { check } from "k6";
import { SERVICES, PRODUCT_IDS } from "../utils/config.js";
import { getToken } from "../utils/multipleAuth.js";
//163*0.7=114/4=28
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 28,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 250,
        },
    },
};

// export const options = {
//     scenarios: {
//         find_breaking_point: {
//             executor: "ramping-arrival-rate",
//             startRate: 5,
//             timeUnit: "1s",
//             preAllocatedVUs: 50,
//             maxVUs: 300,
//             stages: [
//                 { duration: "30s", target: 20 },
//                 { duration: "30s", target: 50 },
//                 { duration: "30s", target: 100 },
//             ],
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
    const resProducts = http.get(`${SERVICES.products}/`, params);
    check(resProducts, {
        "get all products succeeded": (r) => r.status === 200,
    });

    // 2. Get products by category
    const resCategory = http.get(`${SERVICES.products}/category/Electronics`, params);
    check(resCategory, {
        "get products by category succeeded": (r) => r.status === 200,
    });

    // 3. Get product details
    const resDetails = http.get(`${SERVICES.products}/${productId}`, params);
    check(resDetails, {
        "get product details succeeded": (r) => r.status === 200,
    });

    // 4. Get multiple products
    const payload = JSON.stringify({
        ids: [productId, secondProductId]
    });
    const resMultiple = http.post(`${SERVICES.products}/ids`, payload, params);
    check(resMultiple, {
        "get multiple products succeeded": (r) => r.status === 200,
    });
}