import datetime
from typing import List

class Transaction:
    def __init__(self, date: datetime.date, transType: str, paymentDes: str, amount: float, currency: str,category: str):
        self._date = date
        self._transType = transType
        self._paymentDes = paymentDes
        self._amount = amount
        self._currency = currency
        self._category=category

    @property
    def date(self) -> datetime.date:
        return self._date

    @property
    def transType(self) -> str:
        return self._transType

    @property
    def paymentDes(self) -> str:
        return self._paymentDes

    @property
    def amount(self) -> float:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency
    
    @property
    def category(self)->str:
        return self._category

    def __str__(self) -> str:
        return (f"On {self.date}, a {self.transType} of {self.currency}{self.amount:.2f} "
                f"was made for {self.paymentDes}.")


class TransactionList():
    def __init__(self):
        self._transactions: List[Transaction] = []

    @property
    def transactions(self):
        return self._transactions

    @transactions.setter
    def transactions(self, new_transactions: list):
        self._transactions = new_transactions

    def addTransaction(self, trans: Transaction) -> None:
        self.transactions.append(trans)
