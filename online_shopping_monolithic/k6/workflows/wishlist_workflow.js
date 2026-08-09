// import http from "k6/http";
// import { check } from "k6";
// import { BASE_URL, PRODUCT_IDS } from "../utils/config.js";
// import { token } from "../utils/multipleAuth.js";
// export const options = {
//     scenarios: {
//         find_breaking_point: {
//             executor: "ramping-vus",
//             startVUs: 1,
//             stages: [
//                 { duration: "30s", target: 20 },
//                 { duration: "30s", target: 50 },
//                 { duration: "30s", target: 100 },
//             ],
//         },
//     },
// };
// // Adjust these to match your real load requirement.
// // Example: "70% load for 2 minutes" against a max of 50 VUs.
// // const MAX_VUS = 50;
// // const TARGET_VUS = Math.round(MAX_VUS * 0.7); // 70% of max

// // export const options = {
// //     scenarios: {
// //         wishlist_workflow: {
// //             executor: "constant-vus",
// //             vus: TARGET_VUS,
// //             duration: "2m",
// //         },
// //     },
// //     thresholds: {
// //         http_req_failed: ["rate<0.01"],
// //         checks: ["rate>0.99"],
// //     },
// // };

// // Cached per VU so we don't re-authenticate on every single iteration.
// let token;
// let user;

// function getProductForVU() {
//     const index = (__VU - 1) % PRODUCT_IDS.length;
//     return PRODUCT_IDS[index];
// }

// export default function () {
//     if (!token) {
//         user = getUserForVU();
//         token = login(user);
//     }

//     const productId = getProductForVU();

//     const params = {
//         headers: {
//             "Content-Type": "application/json",
//             Authorization: `Bearer ${token}`,
//         },
//     };

//     // 1. Browse Products
//     const browseRes = http.get(`${BASE_URL}/`, params);
//     check(browseRes, {
//         "browse products succeeded": (r) => r.status === 200,
//     });

//     // 2. Add to Wishlist
//     const payload = JSON.stringify({ _id: productId });
//     const addRes = http.put(`${BASE_URL}/wishlist`, payload, params);
//     check(addRes, {
//         "add to wishlist succeeded": (r) => r.status === 200 || r.status === 201,
//     });

//     // 3. View Wishlist
//     const viewRes = http.get(`${BASE_URL}/customer/wishlist`, params);
//     check(viewRes, {
//         "view wishlist succeeded": (r) => r.status === 200,
//         "wishlist contains product": (r) => {
//             try {
//                 const body = r.json();
//                 // Adjust this to match your actual response shape.
//                 return JSON.stringify(body).includes(productId);
//             } catch (e) {
//                 return false;
//             }
//         },
//     });

//     // 4. Delete Wishlist Item
//     const delRes = http.del(`${BASE_URL}/wishlist/${productId}`, null, params);
//     check(delRes, {
//         "delete wishlist item succeeded": (r) => r.status === 200 || r.status === 204,
//     });
// }

import http from "k6/http";
import { check } from "k6";
import { BASE_URL, PRODUCT_IDS } from "../utils/config.js";
import { getToken } from "../utils/multipleAuth.js";

export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 40,             // ≈ 70% of ~231 req/s observed ceiling
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 20,
            maxVUs: 90,
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
    const browseRes = http.get(`${BASE_URL}/`, params);
    check(browseRes, {
        "browse products succeeded": (r) => r.status === 200,
    });

    // 2. Add to Wishlist
    const payload = JSON.stringify({ _id: productId });
    const addRes = http.put(`${BASE_URL}/wishlist`, payload, params);
    check(addRes, {
        "add to wishlist succeeded": (r) => r.status === 200 || r.status === 201,
    });

    // 3. View Wishlist
    const viewRes = http.get(`${BASE_URL}/customer/wishlist`, params);
    check(viewRes, {
        "view wishlist succeeded": (r) => r.status === 200,
        "wishlist contains product": (r) => {
            try {
                const body = r.json();
                return JSON.stringify(body).includes(productId);
            } catch (e) {
                return false;
            }
        },
    });

    // 4. Delete Wishlist Item
    const delRes = http.del(`${BASE_URL}/wishlist/${productId}`, null, params);
    check(delRes, {
        "delete wishlist item succeeded": (r) => r.status === 200 || r.status === 204,
    });
}