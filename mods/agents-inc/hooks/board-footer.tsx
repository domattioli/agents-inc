// Surface module for the Board footer: the one line of valid keys, and the Client that receives the keys.
// Host fact (spike S6): keys reach a Client only after a mouse click on it; before that they go to the chat. So the
// footer shows a dim hint until the first key arrives. Escape never arrives here: the host returns focus.
export default function Footer(props: { keys: string; hint: string }, s: any) {
  if (s.state === undefined) {
    s.onKey((k: any) => {
      s.post({ kind: 'key', key: String(k.key) })
      s.setState({ armed: true })
    })
    s.setState({ armed: false })
  }
  const armed = Boolean(s.state?.armed)
  const text = armed ? props.keys : `${props.keys} · ${props.hint}`
  const room = Number(s.columns) || 0
  return s.elements.Text({ dimColor: true, children: room > 1 && text.length > room ? text.slice(0, room - 1) + '…' : text })
}
