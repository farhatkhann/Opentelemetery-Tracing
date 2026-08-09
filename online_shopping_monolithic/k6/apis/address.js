import http from "k6/http";
import { BASE_URL } from "../utils/config.js";
import { getToken } from "../utils/auth.js";

export default function () {

    const token = getToken();

    const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
    };

    const payload = JSON.stringify({
        street: "MG Road",
        postalCode: "452001",
        city: "Indore",
        country: "India"
    });

    http.post(
        `${BASE_URL}/customer/address`,
        payload,
        { headers }
    );
}