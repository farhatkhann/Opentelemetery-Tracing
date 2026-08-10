const mongoose = require('mongoose');
const { OrderModel, CartModel } = require('../models');
const { v4: uuidv4 } = require('uuid');

//Dealing with data base operations
class ShoppingRepository {

    async Orders(customerId) {

        const orders = await OrderModel.find({ customerId });

        return orders;

    }

    async Cart(customerId) {

        const cartItems = await CartModel.find({ customerId: customerId });


        if (cartItems) {
            return cartItems;
        }

        throw new Error('Data Not found!');
    }

    // async AddCartItem(customerId,item,qty,isRemove){

    //         // return await CartModel.deleteMany();

    //         const cart = await CartModel.findOne({ customerId: customerId })

    //         const { _id } = item;

    //         if(cart){

    //             let isExist = false;

    //             let cartItems = cart.items;


    //             if(cartItems.length > 0){

    //                 cartItems.map(item => {

    //                     if(item.product._id.toString() === _id.toString()){
    //                         if(isRemove){
    //                             cartItems.splice(cartItems.indexOf(item), 1);
    //                          }else{
    //                            item.unit = qty;
    //                         }
    //                          isExist = true;
    //                     }
    //                 });
    //             } 

    //             if(!isExist && !isRemove){
    //                 cartItems.push({product: { ...item}, unit: qty });
    //             }

    //             cart.items = cartItems;

    //             return await cart.save()

    //         }else{

    //            return await CartModel.create({
    //                 customerId,
    //                 items:[{product: { ...item}, unit: qty }]
    //             })
    //         }


    // }

    async AddCartItem(customerId, item, qty, isRemove) {

        const cart = await CartModel.findOne({ customerId: customerId })

        // `item` may arrive as either a plain product-id string or a full
        // product object -- normalize to just the id we actually need.
        const productId = (item && typeof item === 'object') ? item._id : item;

        if (cart) {

            let isExist = false;

            let cartItems = cart.items;


            if (cartItems.length > 0) {

                cartItems.map(cartItem => {

                    if (cartItem.product._id && cartItem.product._id.toString() === productId.toString()) {
                        if (isRemove) {
                            cartItems.splice(cartItems.indexOf(cartItem), 1);
                        } else {
                            cartItem.unit = qty;
                        }
                        isExist = true;
                    }
                });
            }

            if (!isExist && !isRemove) {
                cartItems.push({ product: { _id: productId }, unit: qty });
            }

            cart.items = cartItems;

            return await cart.save()

        } else {

            return await CartModel.create({
                customerId,
                items: [{ product: { _id: productId }, unit: qty }]
            })
        }


    }

    async CreateNewOrder(customerId, txnId) {

        //required to verify payment through TxnId

        const cart = await CartModel.findOne({ customerId: customerId })

        if (cart) {

            let amount = 0;

            let cartItems = cart.items;

            if (cartItems.length > 0) {
                //process Order

                // cartItems.map(item => {
                //     amount += parseInt(item.product.price) * parseInt(item.unit);
                // });

                cartItems.map(item => {
                    const price = parseInt(item.product.price) || 0;
                    const unit = parseInt(item.unit) || 0;
                    amount += price * unit;
                });

                const orderId = uuidv4();

                const order = new OrderModel({
                    orderId,
                    customerId,
                    amount,
                    status: 'received',
                    items: cartItems
                })

                cart.items = [];

                const orderResult = await order.save();
                await cart.save();
                return orderResult;


            }



        }

        return {}
    }

}

module.exports = ShoppingRepository;
