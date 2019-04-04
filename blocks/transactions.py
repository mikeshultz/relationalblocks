""" consumer.py is what stuffs the DB """
import os
import random
import threading
from eth_utils.hexadecimal import encode_hex
from .config import DSN, JSONRPC_NODE, LOGGER
from .db import TransactionModel
from web3 import Web3, HTTPProvider

log = LOGGER.getChild(__name__)


class StoreTransactions(threading.Thread):
    """ Populate tx data for "dirty" transactions in the DB """

    def __init__(self):
        super(StoreTransactions, self).__init__()
        self.model = TransactionModel(DSN)

        if os.environ.get('WEB3_INFURA_API_KEY'):
            from web3.auto.infura import w3 as web3
            self.web3 = web3
        else:
            self.web3 = Web3(HTTPProvider(JSONRPC_NODE))

        self.shutdown = threading.Event()

    def get_transaction(self, tx_hash):
        """ Gets a tx from the chain """

        log.debug("Fetching transaction %s", tx_hash)

        if not isinstance(tx_hash, str):
            raise ValueError("tx_hash must be an integer")

        return self.web3.eth.getTransaction(tx_hash)

    def get_dirty_transaction(self):
        """ Gets a tx that needs to be populated """

        res = self.model.get_random_dirty()

        if not res:
            return None

        return self.web3.eth.getTransaction(res[0]['hash'])

    def process_transactions(self):
        """ Process the transactions from the chain """

        log.debug("process_transactions...")

        while True:

            # If we've been told to shutdown...
            if self.shutdown.is_set():
                log.info("Shutting down gracefully...")
                break

            tx = self.get_dirty_transaction()

            if not tx:
                log.debug("No dirty transactions")
                break

            log.debug("Processing transaction {}".format(tx['hash'].hex()))

            self.model.query(
                "UPDATE transaction SET "
                " dirty = false,"
                " block_number = {0},"
                " from_address = {1},"
                " to_address = {2},"
                " value = {3},"
                " gas_price = {4},"
                " gas_limit = {5},"
                " nonce = {6},"
                " input = {7}"
                " WHERE hash = {8};",
                tx['blockNumber'],
                tx['from'],
                tx['to'],
                tx['value'],
                tx['gasPrice'],
                tx['gas'],
                tx['nonce'],
                tx['input'],
                tx['hash'].hex(),
                commit=True
            )

    def run(self):
        """ Kick off the process """

        log.info("Starting transaction consumer...")

        self.process_transactions()
