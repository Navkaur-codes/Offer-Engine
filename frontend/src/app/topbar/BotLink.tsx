import { QrCode } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { botUrl, FALLBACK_BOT } from '@/lib/bot'
import { useMeta } from '@/lib/queries'

export function BotLink() {
  const { data } = useMeta()
  const username = data?.bot_username ?? FALLBACK_BOT
  const url = botUrl(username)
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Open the Telegram bot link and QR code">
          <QrCode />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 text-center">
        <div className="mx-auto w-fit rounded-[6px] bg-white p-2">
          <QRCodeSVG value={url} size={160} fgColor="#0A0A0B" bgColor="#FFFFFF" level="M" title={`QR code for ${url}`} />
        </div>
        <p className="num mt-3 text-[13px] text-ink">@{username}</p>
        <p className="mt-1 text-[12px] text-muted">Scan to get offers as a customer would.</p>
        <Button asChild variant="secondary" className="mt-3 w-full">
          <a href={url} target="_blank" rel="noreferrer">
            Open in Telegram ↗
          </a>
        </Button>
        {data?.lab_group_link ? (
          <a href={data.lab_group_link} target="_blank" rel="noreferrer" className="mt-2 block text-[12px] text-muted underline-offset-2 hover:underline">
            Customer Lab group ↗
          </a>
        ) : null}
      </PopoverContent>
    </Popover>
  )
}
