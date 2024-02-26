from mesa import Agent, Model
from mesa.time import RandomActivation
import random
from threading import Lock

class Product:
    def __init__(self, name, seller_starting_price, reserve_price):
        self.name = name
        self.starting_price = seller_starting_price
        self.reserve_price = reserve_price
        self.highest_bid = seller_starting_price
        self.highest_bidder = None

    def bid(self, price, bidder):
        if price > self.highest_bid:
            self.highest_bid = price
            self.highest_bidder = bidder

class Seller(Agent):
    def __init__(self, unique_id, model, product, seller_starting_price):
        super().__init__(unique_id, model)
        self.product = product
        self.current_price = seller_starting_price
        self.timer = 0
        self.finished = False
        self.lock = Lock()  # Lock for synchronized access
       
    def ask_price(self):
        return self.current_price
    
    def receive_message(self, message):
        if message['type'] == 'bid':
            self.product.bid(message['price'], message['buyer'])
            print(f"Seller {self.unique_id} received bid of {message['price']} from buyer {message['buyer'].name}")

    def step(self):
        with self.lock:    
            if not self.finished:
                if self.timer == 0:
                    print("Vendor started.")
                self.timer += 1
                if self.timer == 1:
                    print(f"Seller: Offer a price for the item for sale (reserve price): {self.current_price}")
                    self.product.reserve_price = self.current_price
                elif self.timer % 2 == 0:
                    print(f"Seller is considering bids")
                    highest_bid = self.product.highest_bid
                    for buyer in self.model.buyers:
                        if buyer.max_bid > highest_bid:
                            highest_bid = buyer.max_bid
                            self.product.highest_bidder = buyer
                    self.product.highest_bid = highest_bid
                    self.current_price = highest_bid
                    print(f"Seller is sending current price of {self.product.highest_bid} to all buyers")
                    self.model.broadcast_message({'type': 'current price', 'price': self.product.highest_bid})
                if self.timer == self.model.auction_length:
                    if self.product.highest_bid >= self.product.reserve_price:
                        print(f"Seller: Auction over. Object sold to buyer {self.product.highest_bidder.name} for {self.product.highest_bid} euros.")
                        self.finished = True
                    else:
                        print(f"Seller: Auction over. Item not sold as no bid exceeded reserve price.")
                        self.finished = True
                    self.model.remove_seller(self)

class Buyer(Agent):
    def __init__(self, unique_id, model, name, budget):
        super().__init__(unique_id, model)
        self.name = name
        self.budget = budget
        self.max_bid = 0
        self.timer = 0
        self.finished = False

    def submit_bid(self, price):
        if price > self.budget:
            price = self.budget  # Adjust bid to fit budget
        if price > self.max_bid and price > self.model.seller.product.highest_bid and price > self.model.seller.product.reserve_price:
            if not self.model.seller.finished:
                self.max_bid = price
                print(f"Buyer {self.name} send bid of {self.max_bid} to seller.")
                self.model.broadcast_message({'type': 'bid', 'price': self.max_bid, 'buyer': self})

    def receive_message(self, message):
        if message['type'] == 'current price':
            if message['price'] > self.max_bid and message['price'] <= self.budget:
                self.submit_bid(max(message['price'], self.max_bid))

    def step(self):
        with self.model.lock:
            if not self.finished:
                if self.timer == 0:
                    print(f"Buyer {self.name}: started. Maximum price = {self.budget}")
                if self.timer > 0 and self.timer % 2 == 0:
                    print(f"Buyer {self.name}: current price = {self.max_bid}")
                if self.timer % 2 == 1:
                    self.model.broadcast_message({'type': 'bid request', 'price': self.model.seller.current_price})
                    self.timer += 1

                self.timer += 1
                if self.model.seller.current_price > self.max_bid and self.max_bid < self.budget:
                    bid = self.model.seller.current_price + random.randint(1, 10)
                else:
                    bid = self.max_bid
                try:
                    self.submit_bid(bid)
                    print(f"Buyer {self.name}: current price = {self.max_bid}")
                except ValueError:
                    self.finished = True
                    print(f"Buyer {self.name}: arrested.")
                if self.max_bid > self.model.seller.current_price:
                    self.model.broadcast_message({'type': 'bid', 'price': self.max_bid, 'buyer': self})

class AuctionModel(Model):
    def __init__(self, auction_length, starting_price, reserve_price, buyers_data):
        self.auction_length = auction_length
        self.schedule = RandomActivation(self)
        self.product = Product('Test Product', starting_price, reserve_price)
        self.seller = Seller(1, self, self.product, starting_price)
        self.schedule.add(self.seller)
        self.buyers = []
        for i, buyer_data in enumerate(buyers_data, start=2):
            name, budget = buyer_data
            self.buyers.append(Buyer(i, self, name, budget))
            self.schedule.add(self.buyers[-1])
        self.lock = Lock()

    def broadcast_message(self, message):
        for agent in self.schedule.agents:
            agent.receive_message(message)

    def remove_seller(self, seller):
        self.schedule.remove(seller)

    def remove_buyer(self, buyer):
        self.schedule.remove(buyer)

    def step(self):
        self.schedule.step()

auction_length = 10
starting_price = 80
reserve_price = 100
buyers_data = [('James', 100), ('Kylie', 150), ('Jorge', 200), ('Emma', 120)]

model = AuctionModel(auction_length, starting_price, reserve_price, buyers_data)

while not model.seller.finished:
    model.step()

print("Auction ended")

for buyer in model.buyers:
    print(f"Buyer {buyer.name} {'arrested' if buyer.finished else 'stopped'}.")
