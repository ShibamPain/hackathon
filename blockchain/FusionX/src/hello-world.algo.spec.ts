import { TestExecutionContext } from '@algorandfoundation/algorand-typescript-testing'
import { describe, expect, it } from 'vitest'
import { HelloWorld } from './hello-world.algo'

describe('HelloWorld contract', () => {
  const ctx = new TestExecutionContext()

  it('returns a greeting', () => {
    const contract = ctx.contract.create(HelloWorld)
    const result = contract.hello('Sally')
    expect(result).toBe('Hello, Sally')
  })
})
