from uuid import uuid4

class Tx:
    
    def __init__(self, id, tx_ins, tx_outs):
        self.id = id
        self.tx_ins = tx_ins
        self.tx_outs = tx_outs

    def sign_input(self, index, private_key):
        message = self.tx_ins[index].spend_message
        signature = private_key.sign(message)
        self.tx_ins[index].signature = signature


class TxIn:

    def __init__(self, tx_id, index, signature):
        self.tx_id = tx_id
        self.index = index
        self.signature = signature

    @property
    def spend_message(self):
        return f"{self.tx_id}:{self.index}".encode()


class TxOut:

    def __init__(self, tx_id, index, amount, public_key):
        self.tx_id = tx_id
        self.index = index
        self.amount = amount
        self.public_key = public_key


class Bank:

    def __init__(self):
        self.txs = {}

    def issue(self, amount, public_key):
        id = uuid4()
        tx_ins = []

        tx_outs = [TxOut(tx_id = id, index = 0, amount = amount, public_key =
                        public_key)]
    
        tx = Tx(id=id, tx_ins = tx_ins, tx_outs = tx_outs)
        self.txs[tx.id] = tx
        return tx

    def validate_tx(self, tx):
        input_sum = 0
        output_sum = 0
        
        for input_one in tx.tx_ins:
            assert self.is_unspent(input_one)
            
            tx_out = self.txs[input_one.tx_id].tx_outs[input_one.index]
            public_key = tx_out.public_key

            public_key.verify(input_one.signature, input_one.spend_message)

            input_sum += tx_out.amount

        for output in tx.tx_outs:
            output_sum += output.amount
            
        assert input_sum == output_sum               

    def is_unspent(self, tx_in):
        for tx in self.txs.values():
            for _tx_in in tx.tx_ins:
                if tx_in.tx_id == _tx_in.tx_id and \
                   tx_in.index == _tx_in.index:
                    return False
        return True


    def handle_tx(self, tx):
        self.validate_tx(tx)
        self.txs[tx.id] = tx

    def fetch_utxo(self, public_key):
        # Find which (tx_id, index) pairs have been spent
        spent_pairs = [(tx_in.tx_id, tx_in.index) 
                        for tx in self.txs.values() 
                        for tx_in in tx.tx_ins]
        # Return tx_outs associated with public_key and not in ^^ list
        return [tx_out for tx in self.txs.values() 
                   for i, tx_out in enumerate(tx.tx_outs)
                       if public_key.to_string() == tx_out.public_key.to_string()
                       and (tx.id, i) not in spent_pairs]

    def fetch_balance(self, public_key):
        # Fetch utxo associated with this public key
        unspents = self.fetch_utxo(public_key)
        # Sum the amounts
        return sum([tx_out.amount for tx_out in unspents])
