import algosdk from 'algosdk'

/** Exports the richest account from LocalNet's default KMD wallet. */
export async function getLocalNetDispenser(algod: algosdk.Algodv2): Promise<algosdk.Account> {
  const kmd = new algosdk.Kmd(
    process.env.KMD_TOKEN ?? process.env.ALGOD_TOKEN ?? 'a'.repeat(64),
    process.env.KMD_SERVER ?? process.env.ALGOD_SERVER ?? 'http://localhost',
    process.env.KMD_PORT ?? '4002',
  )
  const { wallets } = await kmd.listWallets()
  const wallet = wallets.find((w: { name: string }) => w.name === 'unencrypted-default-wallet')
  if (!wallet) throw new Error('LocalNet default wallet not found. Is LocalNet running? Try: vibekit localnet start')

  const { wallet_handle_token: handle } = await kmd.initWalletHandle(wallet.id, '')
  try {
    const { addresses } = await kmd.listKeys(handle)
    const balances = await Promise.all(
      addresses.map(async (addr: string) => ({ addr, amount: (await algod.accountInformation(addr).do()).amount })),
    )
    const richest = balances.reduce((max, acc) => (acc.amount > max.amount ? acc : max))
    const { private_key: sk } = await kmd.exportKey(handle, '', richest.addr)
    return { addr: algosdk.Address.fromString(richest.addr), sk }
  } finally {
    await kmd.releaseWalletHandle(handle)
  }
}
