import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = "http://localhost:8080";
//49*0.7=34
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 34,             
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 10,   
            maxVUs: 300,          
        },
    },
};

export default function () {

    const id = Math.floor(Math.random() * 100000);

    const payload = JSON.stringify({
        firstName: "John",
        lastName: "Doe" + id,
        address: "New Street",
        city: "Delhi",
        telephone: "9876543210"
    });

    const params = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const res = http.post(
        `${BASE_URL}/api/customer/owners`,
        payload,
        params
    );

    check(res, {
        'Owner created': (r) => r.status === 201,
    });

    sleep(1);
}