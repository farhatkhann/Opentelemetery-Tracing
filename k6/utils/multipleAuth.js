import http from "k6/http";
import { SERVICES } from "./config.js";

const params = {
    headers: {
        "Content-Type": "application/json"
    }
};

/**
 * Signs up a brand-new, guaranteed-unique account for this VU.
 * Unique per VU (not per iteration) since this only needs to run once --
 * the resulting token is cached and reused across that VU's iterations.
 */
function signup() {
    const email = `loadtest_vu${__VU}_${Date.now()}@test.com`;
    const password = "123456";

    const payload = JSON.stringify({
        email,
        password,
        phone: "9876543210"
    });

    const res = http.post(`${SERVICES.customer}/signup`, payload, params);

    if (res.status !== 200 && res.status !== 201) {
        throw new Error(`Signup failed for VU ${__VU}: status ${res.status} body ${res.body}`);
    }

    return { email, password };
}

function login(user) {
    const payload = JSON.stringify({
        email: user.email,
        password: user.password
    });

    const res = http.post(`${SERVICES.customer}/login`, payload, params);

    if (res.status !== 200) {
        throw new Error(`Login failed for ${user.email}: status ${res.status}`);
    }

    return res.json("token");
}

// Cached per VU -- signup + login happen once per VU, not once per iteration.
let cachedToken;

/**
 * Returns a token for this VU. On first call, creates a fresh unique
 * account and logs in. On every subsequent call (same VU), returns the
 * cached token instantly -- no repeated signup/login overhead, and no
 * two VUs ever share an account.
 */
export function getToken() {
    if (!cachedToken) {
        const user = signup();
        cachedToken = login(user);
    }
    return cachedToken;
}