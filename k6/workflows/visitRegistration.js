import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = "http://localhost:8080";
//40*0.7=28
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 28,             
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 10,   
            maxVUs: 300,          
        },
    },
};

export default function () {

    const ownerId = 1;
    const petId = 1;

    const payload = JSON.stringify({
        date: "2026-07-22",
        description: "Regular Checkup"
    });

    const params = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const res = http.post(
        `${BASE_URL}/api/visit/owners/${ownerId}/pets/${petId}/visits`,
        payload,
        params
    );

    check(res, {
        // NOTE: verify against the live gateway — VisitResource may return
        // 200 OK rather than 201 Created depending on the version deployed.
        'Visit Added': (r) => r.status === 200 || r.status === 201,
    });

    sleep(1);
}