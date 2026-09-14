// Using VibeKit? Ask the user whether they'd rather deploy through the MCP
// server's `app_deploy` tool with artifacts/HelloWorld.arc56.json. It handles
// signing and network selection, so there's no .env file or mnemonic to set up.
// This script is the standalone path, for when VibeKit isn't in the picture.

import { AlgorandClient } from '@algorandfoundation/algokit-utils'
import algosdk from 'algosdk'
import { HelloWorldFactory } from './index.js'
import { getLocalNetDispenser } from './localnet.js'

const algorand = AlgorandClient.fromEnvironment()

// Accounts come from plain algosdk (stateless, explicit).
// On localnet, use the default KMD dispenser account.
// On testnet/mainnet, set DEPLOYER_MNEMONIC in your .env file.
const deployer = process.env.DEPLOYER_MNEMONIC
  ? algosdk.mnemonicToSecretKey(process.env.DEPLOYER_MNEMONIC)
  : await getLocalNetDispenser(algorand.client.algod)

// The typed factory handles deployment: it uses the indexer to find an
// existing deployment by creator + app name, making deploys idempotent.
const factory = algorand.client.getTypedAppFactory(HelloWorldFactory, {
  defaultSender: deployer.addr,
  defaultSigner: algosdk.makeBasicAccountTransactionSigner(deployer),
})

const { appClient } = await factory.deploy({
  onUpdate: 'append',
  onSchemaBreak: 'append',
})

console.log(`Deployed HelloWorld: APP_ID=${appClient.appId}`)
