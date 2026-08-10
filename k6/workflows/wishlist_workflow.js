import http from "k6/http";
import { check } from "k6";
import { SERVICES, PRODUCT_IDS } from "../utils/config.js";
import { getToken } from "../utils/multipleAuth.js";
//164.29*0.7=114.8/4=28.7
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
            Authorization: `Bearer ${token}`,
        },
    };

    // 1. Browse Products
    const browseRes = http.get(`${SERVICES.products}/`, params);
    check(browseRes, {
        "browse products succeeded": (r) => r.status === 200,
    });

    // 2. Add to Wishlist
    const payload = JSON.stringify({ _id: productId });
    const addRes = http.put(`${SERVICES.products}/wishlist`, payload, params);
    check(addRes, {
        "add to wishlist succeeded": (r) => r.status === 200 || r.status === 201,
    });

    // 3. View Wishlist
    const viewRes = http.get(`${SERVICES.customer}/wishlist`, params);
    check(viewRes, {
        "view wishlist succeeded": (r) => r.status === 200,
        // "wishlist contains product": (r) => {
        //     try {
        //         const body = r.json();
        //         return JSON.stringify(body).includes(productId);
        //     } catch (e) {
        //         return false;
        //     }
        // },
    });

    // 4. Delete Wishlist Item
    const delRes = http.del(`${SERVICES.products}/wishlist/${productId}`, null, params);
    check(delRes, {
        "delete wishlist item succeeded": (r) => r.status === 200 || r.status === 204,
    });
}