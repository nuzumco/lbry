import json
from binascii import hexlify
from lbrynet.testcase import CommandTestCase


class ResolveCommand(CommandTestCase):

    def get_claim_id(self, tx):
        return tx['outputs'][0]['claim_id']

    async def assertResolvesToClaimId(self, name, claim_id):
        other = (await self.resolve(name))[name]
        if claim_id is None:
            self.assertIn('error', other)
        else:
            self.assertEqual(claim_id, other['claim_id'])

    async def test_resolve_response(self):
        channel_id = self.get_claim_id(
            await self.channel_create('@abc', '0.01')
        )

        # resolving a channel @abc
        response = await self.resolve('lbry://@abc')
        self.assertSetEqual({'lbry://@abc'}, set(response))
        self.assertEqual(response['lbry://@abc']['name'], '@abc')
        self.assertEqual(response['lbry://@abc']['value_type'], 'channel')
        self.assertEqual(response['lbry://@abc']['meta']['claims_in_channel'], 0)

        await self.stream_create('foo', '0.01', channel_id=channel_id)
        await self.stream_create('foo2', '0.01', channel_id=channel_id)

        # resolving a channel @abc with some claims in it
        response['lbry://@abc']['confirmations'] += 2
        response['lbry://@abc']['meta']['claims_in_channel'] = 2
        self.assertEqual(response, await self.resolve('lbry://@abc'))

        # resolving claim foo within channel @abc
        response = await self.resolve('lbry://@abc/foo')
        self.assertSetEqual({'lbry://@abc/foo'}, set(response))
        claim = response['lbry://@abc/foo']
        self.assertEqual(claim['name'], 'foo')
        self.assertEqual(claim['value_type'], 'stream')
        self.assertEqual(claim['signing_channel']['name'], '@abc')
        self.assertTrue(claim['is_channel_signature_valid'])
        self.assertEqual(
            claim['timestamp'],
            self.ledger.headers[claim['height']]['timestamp']
        )
        self.assertEqual(
            claim['signing_channel']['timestamp'],
            self.ledger.headers[claim['signing_channel']['height']]['timestamp']
        )

        # resolving claim foo by itself
        self.assertEqual(claim, (await self.resolve('lbry://foo'))['lbry://foo'])
        # resolving from the given permanent url
        permanent_url = response['lbry://@abc/foo']['permanent_url']
        self.assertEqual(claim, (await self.resolve(permanent_url))[permanent_url])

        # resolving multiple at once
        response = await self.resolve(['lbry://foo', 'lbry://foo2'])
        self.assertSetEqual({'lbry://foo', 'lbry://foo2'}, set(response))
        claim = response['lbry://foo2']
        self.assertEqual(claim['name'], 'foo2')
        self.assertEqual(claim['value_type'], 'stream')
        self.assertEqual(claim['signing_channel']['name'], '@abc')
        self.assertTrue(claim['is_channel_signature_valid'])

        # resolve has correct confirmations
        tx_details = await self.blockchain.get_raw_transaction(claim['txid'])
        self.assertEqual(claim['confirmations'], json.loads(tx_details)['confirmations'])

        # resolve handles invalid data
        await self.blockchain_claim_name("gibberish", hexlify(b"{'invalid':'json'}").decode(), "0.1")
        await self.generate(1)
        response = await self.resolve("lbry://gibberish")
        self.assertSetEqual({'lbry://gibberish'}, set(response))
        claim = response['lbry://gibberish']
        self.assertEqual(claim['name'], 'gibberish')
        self.assertNotIn('value', claim)

    async def test_winning_by_effective_amount(self):
        # first one remains winner unless something else changes
        claim_id1 = self.get_claim_id(
            await self.channel_create('@foo', allow_duplicate_name=True))
        await self.assertResolvesToClaimId('@foo', claim_id1)
        claim_id2 = self.get_claim_id(
            await self.channel_create('@foo', allow_duplicate_name=True))
        await self.assertResolvesToClaimId('@foo', claim_id1)
        claim_id3 = self.get_claim_id(
            await self.channel_create('@foo', allow_duplicate_name=True))
        await self.assertResolvesToClaimId('@foo', claim_id1)
        # supports change the winner
        await self.support_create(claim_id3, '0.09')
        await self.assertResolvesToClaimId('@foo', claim_id3)
        await self.support_create(claim_id2, '0.19')
        await self.assertResolvesToClaimId('@foo', claim_id2)
        await self.support_create(claim_id1, '0.19')
        await self.assertResolvesToClaimId('@foo', claim_id1)

    async def test_advanced_resolve(self):
        claim_id1 = self.get_claim_id(
            await self.stream_create('foo', '0.7', allow_duplicate_name=True))
        claim_id2 = self.get_claim_id(
            await self.stream_create('foo', '0.8', allow_duplicate_name=True))
        claim_id3 = self.get_claim_id(
            await self.stream_create('foo', '0.9', allow_duplicate_name=True))
        # plain winning claim
        await self.assertResolvesToClaimId('foo', claim_id3)
        # sequence resolution
        await self.assertResolvesToClaimId('foo:1', claim_id1)
        await self.assertResolvesToClaimId('foo:2', claim_id2)
        await self.assertResolvesToClaimId('foo:3', claim_id3)
        await self.assertResolvesToClaimId('foo:4', None)
        # amount order resolution
        await self.assertResolvesToClaimId('foo$1', claim_id3)
        await self.assertResolvesToClaimId('foo$2', claim_id2)
        await self.assertResolvesToClaimId('foo$3', claim_id1)
        await self.assertResolvesToClaimId('foo$4', None)
