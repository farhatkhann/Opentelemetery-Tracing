FROM node

WORKDIR /app/products

COPY package.json .

RUN npm install
RUN npm rebuild bcrypt --build-from-source

COPY . .

EXPOSE 8002

CMD ["npm", "start"]