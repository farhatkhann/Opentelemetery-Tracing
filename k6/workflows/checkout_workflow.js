import http from "k6/http";
import { check } from "k6";
import {
    SERVICES,
    PRODUCT_IDS,
    QUANTITY,
    TAX_NUMBER
} from "../utils/config.js";
import { getToken } from "../utils/multipleAuth.js";
//187*0.7=130/5=26
export const options = {
    scenarios: {
        fixed_load: {
            executor: "constant-arrival-rate",
            rate: 26,           
            timeUnit: "1s",
            duration: "2m",
            preAllocatedVUs: 40,
            maxVUs: 250,
        },
    },
};

function getProductForVU() {
    const index = (__VU - 1) % PRODUCT_IDS.length;
    return PRODUCT_IDS[index];
}

export default function () {
    const token = getToken();
    const productId = getProductForVU();

    const params = {
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        }
    };

    // 1. Browse Products
    const browseRes = http.get(`${SERVICES.products}/`, params);
    check(browseRes, {
        "browse products succeeded": (r) => r.status === 200,
    });

    // 2. Add Product to Cart
    // NOTE: the /cart route expects `_id`, not `productId` (see products.js).
    const cartPayload = JSON.stringify({
        _id: productId,
        qty: QUANTITY
    });
    const addRes = http.put(`${SERVICES.shopping}/cart`, cartPayload, params);
    check(addRes, {
        "add to cart succeeded": (r) => r.status === 200 || r.status === 201,
    });

    // 3. View Cart
    const viewCartRes = http.get(`${SERVICES.shopping}/cart`, params);
    check(viewCartRes, {
        "view cart succeeded": (r) => r.status === 200,
    });

    // 4. Place Order
    const orderPayload = JSON.stringify({
        txnNumber: TAX_NUMBER
    });
    const orderRes = http.post(`${SERVICES.shopping}/order`, orderPayload, params);
    check(orderRes, {
        "place order succeeded": (r) => r.status === 200,
    });

    // 5. View Orders
    const ordersRes = http.get(`${SERVICES.shopping}/orders`, params);
    check(ordersRes, {
        "view orders succeeded": (r) => r.status === 200,
    });
}