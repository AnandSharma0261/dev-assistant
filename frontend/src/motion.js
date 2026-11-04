// Framer Motion variants — results cards ek-ek karke (stagger) andar aayenge
export const container = { hidden: {}, show: { transition: { staggerChildren: 0.1 } } }
export const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } },
}
