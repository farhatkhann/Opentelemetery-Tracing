import http from "k6/http";
import { SERVICES, USER } from "../utils/config.js";
import { check } from "k6";
//35.71*0.7=24.9
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 24,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 250,
        },
    },
};

export default function () {
    const payload = JSON.stringify({
        email: USER.email,
        password: USER.password
    });

    const params = {
        headers: {
            "Content-Type": "application/json"
        }
    };

    const res = http.post(
        `${SERVICES.customer}/login`,
        payload,
        params
    );

    check(res, {
        "login successful": (r) => r.status === 200,
    });

    if (res.status !== 200) {
        throw new Error("Login failed");
    }
}