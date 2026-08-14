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

    const payload = JSON.stringify({
        firstName: "James",
        lastName: "Updated",
        address: "Updated Address",
        city: "Mumbai",
        telephone: "9999999999"
    });

    const params = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const res = http.put(
        `${BASE_URL}/api/customer/owners/${ownerId}`,
        payload,
        params
    );

    check(res, {
        // NOTE: verify against the live gateway — some OwnerResource
        // implementations return 204 No Content instead of 200 here.
        'Owner Updated': (r) => r.status === 200 || r.status === 204,
    });

    sleep(1);
}