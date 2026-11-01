import { isWebAddress } from './links'

interface Props {
  url: string
  title: string
  /** Said by screen readers after the title: "opens the official document in a new tab". */
  openLabel: string
  /** Extra classes, e.g. to make the link a full-height touch target. */
  className?: string
}

/**
 * A link to an official document. The address comes from our own registry, which only accepts
 * https, but it is checked again here: an address that is not a web page is shown as plain text,
 * so a bad record in the index can never become a script that runs when someone clicks.
 */
export function OfficialLink({ url, title, openLabel, className = '' }: Props) {
  if (!isWebAddress(url)) return <span>{title}</span>
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`text-brand underline ${className}`}
    >
      {title}
      {/* The space is outside the hidden text: at the start of it, it would be dropped. */}{' '}
      <span className="sr-only">({openLabel})</span>
    </a>
  )
}
