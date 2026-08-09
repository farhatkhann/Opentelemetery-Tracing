import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
import { getToken } from "../utils/auth.js";
import { check } from "k6";

// export const options = {
//     vus: 5,
//     duration: '2m',
// };

export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 91,   // ≈ 70% of saturation (259.56 req/s @ 5 VUs)
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 20,
            maxVUs: 350,
        },
    },
};

export function setup() {
    const token = getToken();

    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    // Create the address ONCE here, not in default(). This keeps
    // populate("address") query size constant for the whole run
    // instead of growing with every iteration.
    const addressPayload = JSON.stringify({
        street: "MG Road",
        postalCode: "452001",
        city: "Indore",
        country: "India"
    });
    const addressRes = http.post(`${BASE_URL}/customer/address`, addressPayload, params);
    check(addressRes, { "setup: address 200": (r) => r.status === 200 });

    return { token };
}

export default function (data) {
    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${data.token}`
        }
    };

    // Only reads now — no more repeated POSTs during the loop
    const profileRes = http.get(`${BASE_URL}/customer/profile`, params);
    check(profileRes, { "profile 200": (r) => r.status === 200 });

    const shoppingRes = http.get(`${BASE_URL}/customer/shoping-details`, params);
    check(shoppingRes, { "shopping-details 200": (r) => r.status === 200 });
}