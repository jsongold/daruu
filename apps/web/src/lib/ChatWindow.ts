export type ActivityRole = "user" | "agent" | "system"

export interface ActivityEntry {
  id: string
  role: ActivityRole
  text: string
  timestamp: string
}

/**
 * ChatWindow accumulates activity entries from any mode.
 * Consumers subscribe to react to changes; drain() flushes all entries.
 */
export class ChatWindow {
  private _entries: ActivityEntry[] = []
  private _listeners = new Set<() => void>()

  add(role: ActivityRole, text: string): void {
    this._entries = [
      ...this._entries,
      { id: crypto.randomUUID(), role, text, timestamp: new Date().toISOString() },
    ]
    this._notify()
  }

  /** Bulk-load persisted entries without triggering re-persist. */
  load(entries: ActivityEntry[]): void {
    this._entries = [...entries]
    this._notify()
  }

  /** Return all entries and clear the window. */
  drain(): ActivityEntry[] {
    const all = this._entries
    this._entries = []
    this._notify()
    return all
  }

  get entries(): readonly ActivityEntry[] {
    return this._entries
  }

  subscribe(fn: () => void): () => void {
    this._listeners.add(fn)
    return () => this._listeners.delete(fn)
  }

  private _notify(): void {
    this._listeners.forEach((fn) => fn())
  }
}
