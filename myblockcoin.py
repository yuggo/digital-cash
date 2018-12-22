"""
BlockCoin

Usage:
  myblockcoin.py serve 
  myblockcoin.py ping 
  myblockcoin.py balance <name> 
  myblockcoin.py tx <from> <to> <amount>
  

Options:
  -h --help     Show this screen.
"""

from uuid import uuid4
from utils import serialize, deserialize, prepare_simple_tx
from identities import user_public_key, user_private_key, bank_public_key
from docopt import docopt
import time

NUM_BANKS = 3

def spend_message(tx, index):
    tx_in = tx.tx_ins[index]
    outpoint = tx_in.outpoint
    return serialize(outpoint) + serialize(tx.tx_outs)

class Tx:
    
    def __init__(self, id, tx_ins, tx_outs):
        self.id = id
        self.tx_ins = tx_ins
        self.tx_outs = tx_outs

    def sign_input(self, index, private_key):
        message = spend_message(self, index)
        signature = private_key.sign(message)
        self.tx_ins[index].signature = signature

    def verify_input(self, index, public_key):
        tx_in = self.tx_ins[index]
        message = spend_message(self, index)
        return public_key.verify(tx_in.signature, message)
    
class Block:
    
    def __init__(self, txns, timestamp = None, signature=None):
        if timestamp == None:
            timestamp = time.time()
        self.timestamp = timestamp
        self.signature = signature
        self.txns = txns

    @property
    def message(self):
        data = [self.timestamp, self.txns]
        return serialize(data)

    def sign(self, private_key):
        self.signature = private_key.sign(self.message)

class TxIn:

    def __init__(self, tx_id, index, signature):
        self.tx_id = tx_id
        self.index = index
        self.signature = signature


    @property
    def outpoint(self):
        return (self.tx_id, self.index)

class TxOut:

    def __init__(self, tx_id, index, amount, public_key):
        self.tx_id = tx_id
        self.index = index
        self.amount = amount
        self.public_key = public_key

    @property
    def outpoint(self):
        return (self.tx_id, self.index)

class Bank:

    def __init__(self, id, private_key):
        self.id = id
        self.private_key = private_key
        self.blocks = []
        self.utxo_set = {}
        self.mempool = []

    @property
    def next_id(self):
        return len(self.blocks) % NUM_BANKS

    def update_utxo(self, tx):
        for tx_in in tx.tx_ins:
            del self.utxo[tx_in.outpoint]

        for tx_out in tx.tx_outs:
            self.utxo[tx_out.outpoint] = tx_out


    def issue(self, amount, public_key):
        id = uuid4()
        tx_ins = []

        tx_outs = [TxOut(tx_id = id, index = 0, amount = amount, public_key =
                        public_key)]
    
        tx = Tx(id=id, tx_ins = tx_ins, tx_outs = tx_outs)
        self.update_utxo(tx)
        return tx

    def validate_tx(self, tx):
        input_sum = 0
        output_sum = 0
        
        for index, input_one in enumerate(tx.tx_ins):
            assert input_one.outpoint in self.utxo
            
            tx_out = self.utxo[input_one.outpoint]
            public_key = tx_out.public_key

            tx.verify_input(index, public_key)

            input_sum += tx_out.amount

        for output in tx.tx_outs:
            output_sum += output.amount
            
        assert input_sum == output_sum               

    def handle_tx(self, tx):
        self.validate_tx(tx)
        self.update_utxo(tx)

    def handle_block(self, block):

        # verify bank sig if heigt > 0
        if len(self.blocks) > 0:
            public_key = bank_public_key(self.next_id)
            public_key.verify(block.signature, block.message)
        # verify all tx
        for tx in block.txns:
            self.validate(tx)
        # update utxo set
        for tx in block.txns:
            self.update_utxo_set(tx)
        # clean mempool
        # TODO
        # update self.blocks
        self.blocks.append(block)
        # schedule next block
        self.schedule_next_block()

    def fetch_utxo(self, public_key):
        return [utxo for utxo in self.utxo.values() if \
                utxo.public_key.to_string() == public_key.to_string()]
    
    def fetch_balance(self, public_key):
        # Fetch utxo associated with this public key
        unspents = self.fetch_utxo(public_key)
        # Sum the amounts
        return sum([tx_out.amount for tx_out in unspents])

    def schedule_next_block(self):
        pass

def prepare_message(command, data):
    return {
        "command":command,
        "data":data,
    }


import sys
import socketserver, socket

host = "0.0.0.0"
port = 10000
address = (host, port)
bank = None

class MyTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

class TCPHandler(socketserver.BaseRequestHandler):

    def respond(self, command, data):
        response = prepare_message(command, data)
        serialized_response = serialize(response)
        self.request.sendall(serialized_response)

    def handle(self):
        message_data = self.request.recv(5000).strip()
        message = deserialize(message_data)
        print(f"got message: {message}")

        command = message['command']

        if command == "ping":
            self.respond("pong", "")

        if command == "balance":
            public_key = message['data']
            balance = bank.fetch_balance(public_key)
            self.respond("balance-response", balance)

        if command == "utxo":
            public_key = message['data']
            utxo = bank.fetch_utxo(public_key)
            self.respond("utxo-response", utxo)
        
        if command == "tx":
            #bank.handle_tx
            tx = message["data"]
            try:
                bank.handle_tx(tx)
                self.respond("tx-response", data="accepted")
            except:
                self.respond("tx-response", data="rejected")

def serve():
    server = MyTCPServer(address, TCPHandler)
    server.serve_forever()


def send_message(command, data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(address)
    message = serialize(prepare_message(command, data))
    sock.sendall(message)
    message_data = sock.recv(5000)
    message = deserialize(message_data)
    print(f"Received data: {message}")

    return message    

if __name__ == "__main__":
    args = docopt(__doc__)
    print(args)
    if args["ping"]:
        ping()
    elif args["serve"]:
        alice_public_key = user_public_key("alice")
        bank.issue(1000, alice_public_key)
        serve()
    elif args["balance"]:
        name = args["<name>"]
        public_key = user_public_key(name)
        send_message("balance", public_key)
    elif args["tx"]:
        sender_private_key = user_private_key(args["<from>"])
        sender_public_key = sender_private_key.get_verifying_key()
        
        recipient_public_key = user_public_key(args["<to>"])
        amount = int(args["<amount>"])

        # fetch utxo
        utxo_response = send_message("utxo", sender_public_key)
        utxo = utxo_response["data"]

        # prepare
        tx = prepare_simple_tx(utxo, sender_private_key, recipient_public_key,
                               amount)
        # send to bank
        response = send_message("tx", tx)
        print(response)
    else:
        print("invalid command")





