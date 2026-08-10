import http from "k6/http";
import { SERVICES, USER } from "./config.js";

export function getToken() {

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

    if (res.status !== 200) {
        throw new Error("Login failed");
    }

    return res.json("token");
}