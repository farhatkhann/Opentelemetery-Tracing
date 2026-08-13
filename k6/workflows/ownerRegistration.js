import http from 'k6/http';
import { check, sleep } from 'k6';
// import { BASE_URL } from '../utils/config';
const BASE_URL = "http://localhost:8080";
//98*0.7=68
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 68,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 300,
        },
    },
};

export default function () {

    const id = Math.floor(Math.random() * 100000);

    const payload = {
        firstName: "John",
        lastName: "Doe" + id,
        address: "New Street",
        city: "Delhi",
        telephone: "9876543210"
    };

    const headers = {
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    };

    const body = Object.entries(payload)
        .map(([k,v]) => `${k}=${encodeURIComponent(v)}`)
        .join('&');

    const res = http.post(
        `${BASE_URL}/owners/new`,
        body,
        headers
    );

    check(res,{
        'Owner created':(r)=>r.status===200
    });

    sleep(1);
}