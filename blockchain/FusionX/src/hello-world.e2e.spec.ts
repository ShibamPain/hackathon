import { AlgorandClient } from '@algorandfoundation/algokit-utils'
import algosdk from 'algosdk'
import { beforeAll, describe, expect, test } from 'vitest'
import { HelloWorldFactory, type HelloWorldClient } from '../index.js'
import { getLocalNetDispenser } from '../localnet.js'

const algorand = AlgorandClient.fromConfig({
  algodConfig: {
    server: process.env.ALGOD_SERVER ?? 'http://localhost',
    port: process.env.ALGOD_PORT ?? '4001',
    token: process.env.ALGOD_TOKEN ?? 'a'.repeat(64),
  },
})

describe('HelloWorld contract (e2e)', () => {
  let client: HelloWorldClient

  beforeAll(async () => {
    // Account setup uses plain algosdk: fund a fresh throwaway account
    // from the LocalNet dispenser.
    const algod = algorand.client.algod
    const dispenser = await getLocalNetDispenser(algod)
    const testAccount = algosdk.generateAccount()

    const suggestedParams = await algod.getTransactionParams().do()
    const fundTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
      sender: dispenser.addr,
      receiver: testAccount.addr,
      amount: 10_000_000, // 10 ALGO
      suggestedParams,
    })
    const { txid } = await algod.sendRawTransaction(fundTxn.signTxn(dispenser.sk)).do()
    await algosdk.waitForConfirmation(algod, txid, 4)

    // Contract interaction uses the typed client. A bare create gives each
    // test run its own app instance without needing an indexer lookup.
    const factory = algorand.client.getTypedAppFactory(HelloWorldFactory, {
      defaultSender: testAccount.addr,
      defaultSigner: algosdk.makeBasicAccountTransactionSigner(testAccount),
    })
    const { appClient } = await factory.send.create.bare()
    client = appClient
  })

  test('says hello', async () => {
    const result = await client.send.hello({ args: { name: 'World' } })
    expect(result.return).toBe('Hello, World')
  })

  test('simulates hello with correct budget', async () => {
    const result = await client
      .newGroup()
      .hello({ args: { name: 'World' } })
      .hello({ args: { name: 'Jane' } })
      .simulate()

    expect(result.returns[0]).toBe('Hello, World')
    expect(result.returns[1]).toBe('Hello, Jane')
    expect(result.simulateResponse.txnGroups[0].appBudgetConsumed).toBeLessThan(100)
  })
})
