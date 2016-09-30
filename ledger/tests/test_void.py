from datetime import datetime
from decimal import Decimal as D

from django.test import TestCase

from ledger.api.actions import create_transaction
from ledger.api.actions import credit
from ledger.api.actions import debit
from ledger.api.actions import void_transaction
from ledger.exceptions import UnvoidableTransactionException
from ledger.models import LedgerEntry
from ledger.tests.factories import LedgerFactory
from ledger.tests.factories import TransactionFactory
from ledger.tests.factories import TransactionTypeFactory
from ledger.tests.factories import UserFactory


class TestVoidBase(TestCase):
    def setUp(self):
        self.creation_user = UserFactory()
        self.ar_ledger = LedgerFactory()
        self.rev_ledger = LedgerFactory()
        self.creation_user_ar_ledger = LedgerFactory()
        self.ttype = TransactionTypeFactory()


class TestVoidTransaction(TestVoidBase):
    def test_simple_void(self):
        amount = D(100)
        # First record a charge
        txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.rev_ledger),
        ])

        # Then void it
        void_txn = void_transaction(txn, self.creation_user)

        self.assertEqual(void_txn.voids, txn)

        self.assertEqual(self.ar_ledger.get_balance(), D(0))
        self.assertEqual(self.rev_ledger.get_balance(), D(0))

    def test_void_with_non_default_type(self):
        amount = D(100)
        # First record a charge
        txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.rev_ledger),
        ])

        # Then void it
        new_ttype = TransactionTypeFactory()
        void_txn = void_transaction(txn, self.creation_user, type=new_ttype)

        self.assertEqual(void_txn.voids, txn)

        self.assertEqual(self.ar_ledger.get_balance(), D(0))
        self.assertEqual(self.rev_ledger.get_balance(), D(0))

        self.assertEqual(void_txn.type, new_ttype)
        self.assertNotEqual(void_txn.type, txn.type)

    def test_cant_void_twice(self):
        amount = D(100)
        # First record a charge
        txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.rev_ledger),
        ])

        # Then void it
        void_transaction(txn, self.creation_user)

        # Trying to void the same transaction again will not succeed
        self.assertRaises(
            UnvoidableTransactionException,
            void_transaction, txn, self.creation_user)

    def test_can_void_void(self):
        # A void transaction can be voided, thus re-instating the original txn
        amount = D(100)
        # First record a charge
        txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.rev_ledger),
        ])

        # Then void it
        void_txn = void_transaction(txn, self.creation_user)

        self.assertEqual(void_txn.voids, txn)

        # And void the void
        void_void_txn = (void_transaction(void_txn, self.creation_user))
        self.assertEqual(void_void_txn.voids, void_txn)

        self.assertEqual(self.ar_ledger.get_balance(), amount)
        self.assertEqual(self.rev_ledger.get_balance(), -amount)

    def test_void_multiple_charges(self):
        amount_1 = D(100)
        amount_2 = D(200)

        txn_1 = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount_1), ledger=self.ar_ledger),
            LedgerEntry(
                amount=credit(amount_1), ledger=self.rev_ledger),
        ])
        txn_2 = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount_2), ledger=self.ar_ledger),
            LedgerEntry(
                amount=credit(amount_2), ledger=self.rev_ledger),
        ])
        self.assertNotEqual(txn_1, txn_2)

        void_transaction(txn_1, self.creation_user)

        self.assertEqual(self.ar_ledger.get_balance(), amount_2)
        self.assertEqual(self.rev_ledger.get_balance(), -amount_2)

    def test_void_from_create_transaction(self):
        amount = D(100)
        evidence = UserFactory.create_batch(3)
        transaction = create_transaction(
            user=UserFactory(),
            evidence=evidence,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.ar_ledger,
                    amount=credit(amount),
                ),
                LedgerEntry(
                    ledger=self.rev_ledger,
                    amount=debit(amount),
                ),
            ],
        )
        self.assertEqual(self.ar_ledger.get_balance(), credit(amount))
        self.assertEqual(self.rev_ledger.get_balance(), debit(amount))
        voiding_transaction = void_transaction(transaction, self.creation_user)
        self.assertEqual(
            set(tro.related_object for tro
                in voiding_transaction.related_objects.all()),
            set(evidence),
        )
        self.assertEqual(self.ar_ledger.get_balance(), D(0))
        self.assertEqual(self.rev_ledger.get_balance(), D(0))
        self.assertEqual(voiding_transaction.voids, transaction)
        self.assertEqual(
            voiding_transaction.posted_timestamp,
            transaction.posted_timestamp)
        self.assertEqual(
            voiding_transaction.type,
            transaction.type)
        self.assertEqual(
            voiding_transaction.notes,
            'Voiding transaction {}'.format(transaction))

    def test_void_with_overridden_notes_and_type(self):
        amount = D(100)
        evidence = UserFactory.create_batch(3)
        transaction = create_transaction(
            user=UserFactory(),
            evidence=evidence,
            ledger_entries=[
                LedgerEntry(
                    ledger=self.ar_ledger,
                    amount=credit(amount),
                ),
                LedgerEntry(
                    ledger=self.rev_ledger,
                    amount=debit(amount),
                ),
            ],
            type=self.ttype,
        )
        voiding_transaction = void_transaction(
            transaction,
            self.creation_user,
            notes='test notes',
        )
        self.assertEqual(voiding_transaction.notes, 'test notes')
        self.assertEqual(voiding_transaction.type, transaction.type)


class TestVoidTimestamps(TestVoidBase):
    def test_auto_timestamp(self):
        # If a posted_timestamp isn't specified we assume the posted_timestamp
        # is the same as the transaction we're voiding.
        amount = D(100)
        # First record a charge
        charge_txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.rev_ledger),
        ])

        # Then void it
        void_txn = void_transaction(charge_txn, self.creation_user)
        self.assertEqual(charge_txn.posted_timestamp,
                         void_txn.posted_timestamp)

    def test_given_timestamp(self):
        # If a posted_timestamp is given for the void, then use it
        amount = D(100)
        # First record a charge
        charge_txn = TransactionFactory(self.creation_user, ledger_entries=[
            LedgerEntry(amount=debit(amount), ledger=self.ar_ledger),
            LedgerEntry(amount=credit(amount), ledger=self.rev_ledger),
        ])

        # Then void it
        now = datetime.now()
        void_txn = void_transaction(
            charge_txn, self.creation_user,
            posted_timestamp=now)
        self.assertEqual(now, void_txn.posted_timestamp)