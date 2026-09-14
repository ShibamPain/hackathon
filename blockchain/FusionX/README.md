# Algorand Starter: Smart Contracts

Write, compile, test, and deploy Algorand smart contracts in TypeScript.

## Prerequisites

- [Node.js](https://nodejs.org/) >= 24
- [Docker](https://www.docker.com/) and [VibeKit](https://getvibekit.ai) -- to run LocalNet

Compiling and testing needs neither: PuyaTs and the client generator are npm
devDependencies, pinned in the lockfile.

## Getting Started

```bash
npm install
vibekit localnet start

npm run build   # compile to TEAL + generate typed clients
npm test        # unit tests + e2e against LocalNet
```

## Layout

- `src/hello-world.algo.ts` -- the contract
- `src/*.spec.ts` -- unit tests (no network) and e2e tests (LocalNet)
- `artifacts/` -- compiled TEAL, ARC-56 spec, and generated client, committed so
  the package type-checks before a build. `npm run build` overwrites it.
- `index.ts` -- re-exports the client and app spec
- `deploy.ts`, `localnet.ts` -- deploy script and KMD dispenser helper

## Deploying

```bash
cp .env.localnet.example .env.localnet
npm run deploy              # LocalNet
npm run deploy:testnet      # TestNet
npm run deploy:mainnet      # MainNet
# => Deployed HelloWorld: APP_ID=1234
```

LocalNet uses the built-in dispenser, so there's no mnemonic to set. For TestNet
and MainNet, copy the matching template and set `DEPLOYER_MNEMONIC` in it:

```bash
cp .env.testnet.example .env.testnet
```

Don't skip that edit -- an empty `DEPLOYER_MNEMONIC` falls back to the LocalNet
dispenser and fails with a confusing connection error.

Deploys are idempotent, but changing the contract creates a **new app ID** rather
than updating the old one. Only `.env*.example` files are committed.

## Adding a Contract

Add `src/my-contract.algo.ts`, append its `algokit-client-generator generate`
call to the `build` script, then re-export the client from `index.ts`.
