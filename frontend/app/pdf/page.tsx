"use client"

import dynamic from "next/dynamic"

const PdfPageContent = dynamic(() => import("./pdf-content"), { ssr: false })

export default function PdfPage() {
  return <PdfPageContent />
}
