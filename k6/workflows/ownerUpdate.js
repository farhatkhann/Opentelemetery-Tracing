import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || "http://localhost:8080";
//48*0.7=33
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 33,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 300,
        },
    },
};

export default function () {

    const ownerId = 1;

    const payload = {
        firstName: "James",
        lastName: "Updated",
        address: "Updated Address",
        city: "Mumbai",
        telephone: "9999999999"
    };

    const params = {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        redirects: 0 // don't auto-follow the 302, we want to see it
    };

    const body = Object.entries(payload)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&');

    const res = http.post(
        `${BASE_URL}/owners/${ownerId}/edit`,
        body,
        params
    );

    const ok = check(res, {
        'Owner Updated': r => r.status === 302
    });

    if (!ok) {
        console.log(`[Owner Update] status=${res.status}`);
        console.log(`[Owner Update] body=${res.body ? res.body.substring(0, 300) : ''}`);
    }

    sleep(1);

}