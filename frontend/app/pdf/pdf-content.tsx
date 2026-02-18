"use client"

import { useState, useRef, useCallback, useEffect, useMemo } from "react"
import { Document, Page, pdfjs } from "react-pdf"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"
import { Button } from "@/components/ui/button"
import { Upload, Send, Loader2, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, StopCircle, ChevronDown } from "lucide-react"
import { toast } from "sonner"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

// Configure PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

const API_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8020"

interface ChatMessage {
  role: "user" | "assistant" | "thinking"
  content: string
  timestamp: string
}

interface Highlight {
  text: string
  pageNumber?: number
}

function ThinkingBlock({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false)
  const preview = content.length > 150 ? content.substring(0, 150) + "..." : content

  return (
    <div className="max-w-[85%]">
      <div
        className="rounded-lg overflow-hidden"
        style={{ background: "#1a1a1a", borderLeft: "3px solid rgba(139, 92, 246, 0.6)" }}
      >
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1.5 text-xs text-white/40 font-medium hover:text-white/60 transition-colors cursor-pointer w-full px-3 pt-2 pb-1"
        >
          <ChevronDown
            className="w-3 h-3 transition-transform"
            style={{ transform: expanded ? "rotate(0deg)" : "rotate(-90deg)" }}
          />
          Reasoning
        </button>
        {expanded ? (
          <div
            className="px-3 pb-2 text-white/50 text-xs leading-relaxed overflow-y-auto"
            style={{ maxHeight: "300px" }}
          >
            {content}
          </div>
        ) : (
          <div
            className="px-3 pb-2 text-white/50 text-xs italic leading-relaxed cursor-pointer"
            onClick={() => setExpanded(true)}
          >
            {preview}
          </div>
        )}
      </div>
    </div>
  )
}

export default function PdfPageContent() {
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [numPages, setNumPages] = useState<number>(0)
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [scale, setScale] = useState<number>(1.2)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [currentThinking, setCurrentThinking] = useState("")
  const [currentResponse, setCurrentResponse] = useState("")
  const [sdkSessionId, setSdkSessionId] = useState<string | null>(null)
  const [highlights, setHighlights] = useState<Highlight[]>([])

  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, currentThinking, currentResponse])

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages)
    setCurrentPage(1)
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith(".pdf")) {
      toast.error("Please select a PDF file")
      return
    }

    setPdfFile(file)
    setPdfUrl(URL.createObjectURL(file))
    setMessages([])
    setHighlights([])
    setSdkSessionId(null)
    toast.success(`Loaded ${file.name}`)
  }

  // Flexible regex that handles all variations the model might produce:
  //   <<highlight>>text<</highlight>>
  //   <<highlight>text</highlight>>
  //   <<highlight page=5>>text<</highlight>>
  //   <<highlight page=5>text</highlight>>
  const HIGHLIGHT_REGEX = /<<highlight(?:\s+page=(\d+))?>+\s*([\s\S]*?)\s*<+\/highlight>+/g

  const parseHighlights = (text: string): Highlight[] => {
    const found: Highlight[] = []
    let match
    const regex = new RegExp(HIGHLIGHT_REGEX.source, HIGHLIGHT_REGEX.flags)
    while ((match = regex.exec(text)) !== null) {
      const pageNumber = match[1] ? parseInt(match[1], 10) : undefined
      const highlightText = match[2].trim()
      if (highlightText) {
        found.push({ text: highlightText, pageNumber })
      }
    }
    return found
  }

  const cleanHighlightMarkers = (text: string): string => {
    return text.replace(
      new RegExp(HIGHLIGHT_REGEX.source, HIGHLIGHT_REGEX.flags),
      (_match, page, content) => {
        const pageRef = page ? `**Page ${page}:** ` : ""
        return `\n> ${pageRef}${content.trim()}\n`
      }
    )
  }

  // Normalize text for fuzzy matching — strip special chars, collapse whitespace
  const normalize = (s: string): string =>
    s.toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim()

  // Memoized text renderer — only re-creates when highlights or currentPage change
  const customTextRenderer = useMemo(() => {
    return ({ str }: { str: string }) => {
      const strNorm = normalize(str)
      if (strNorm.length < 3) return str

      const pageHighlights = highlights.filter(
        h => !h.pageNumber || h.pageNumber === currentPage
      )
      if (pageHighlights.length === 0) return str

      const isHighlighted = pageHighlights.some(h => {
        const hNorm = normalize(h.text)
        if (hNorm.includes(strNorm)) return true
        if (strNorm.includes(hNorm)) return true
        const hWords = hNorm.split(" ").filter(w => w.length >= 4)
        const sWords = strNorm.split(" ").filter(w => w.length >= 4)
        if (sWords.length > 0 && sWords.every(sw => hWords.some(hw => hw.includes(sw) || sw.includes(hw)))) {
          return true
        }
        return false
      })

      if (isHighlighted) {
        return `<mark style="background-color: rgba(239, 68, 68, 0.35); color: transparent; padding: 2px 0; border-radius: 2px;">${str}</mark>`
      }
      return str
    }
  }, [highlights, currentPage])

  const sendQuestion = useCallback(async () => {
    if (!inputMessage.trim()) return
    if (!pdfFile) {
      toast.error("Please upload a PDF first")
      return
    }

    const question = inputMessage
    setInputMessage("")
    setIsLoading(true)
    setCurrentThinking("")
    setCurrentResponse("")

    // Add user message
    setMessages(prev => [...prev, {
      role: "user",
      content: question,
      timestamp: new Date().toISOString()
    }])

    abortControllerRef.current = new AbortController()

    try {
      const formData = new FormData()
      // Only send file on first question or if no session
      if (!sdkSessionId) {
        formData.append("file", pdfFile)
      }
      formData.append("question", question)
      if (sdkSessionId) {
        formData.append("sdk_session_id", sdkSessionId)
      }

      const response = await fetch(`${API_URL}/pdf/ask`, {
        method: "POST",
        body: formData,
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullResponse = ""
      let fullThinking = ""

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split("\n")

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            const data = line.slice(6)
            if (data === "[DONE]") continue

            try {
              const event = JSON.parse(data)

              switch (event.type) {
                case "thinking":
                  fullThinking += event.content || ""
                  setCurrentThinking(fullThinking)
                  break

                case "text":
                  fullResponse += event.content || ""
                  setCurrentResponse(fullResponse)
                  break

                case "complete":
                  fullResponse = event.content || fullResponse
                  if (event.session_id) {
                    setSdkSessionId(event.session_id)
                  }

                  // Parse highlights from response
                  const newHighlights = parseHighlights(fullResponse)
                  setHighlights(newHighlights)

                  // Auto-navigate to the first highlighted page
                  const firstPageHighlight = newHighlights.find(h => h.pageNumber)
                  if (firstPageHighlight?.pageNumber) {
                    setCurrentPage(firstPageHighlight.pageNumber)
                  }

                  // Clean markers from display text
                  const cleanedResponse = cleanHighlightMarkers(fullResponse)

                  // Add thinking message if we got thinking content
                  if (fullThinking) {
                    setMessages(prev => [...prev, {
                      role: "thinking",
                      content: fullThinking,
                      timestamp: new Date().toISOString()
                    }])
                  }

                  // Add assistant message
                  setMessages(prev => [...prev, {
                    role: "assistant",
                    content: cleanedResponse,
                    timestamp: new Date().toISOString()
                  }])

                  setCurrentThinking("")
                  setCurrentResponse("")
                  break

                case "error":
                  toast.error(event.error || "An error occurred")
                  break
              }
            } catch {
              // Skip unparseable lines
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === "AbortError") {
        // User cancelled
      } else {
        toast.error(`Failed: ${error.message}`)
      }
    } finally {
      setIsLoading(false)
    }
  }, [inputMessage, pdfFile, sdkSessionId])

  const stopGeneration = () => {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    setCurrentThinking("")
    setCurrentResponse("")
  }

  return (
    <section className="w-full h-full flex overflow-hidden" style={{ background: "#111111" }}>
      {/* Left: PDF Viewer */}
      <div className="flex-1 flex flex-col overflow-hidden m-2 mr-1">
        <div className="rounded-sm h-full flex flex-col" style={{ background: "#151515" }}>
          {!pdfUrl ? (
            /* Upload zone */
            <div className="flex-1 flex items-center justify-center">
              <div
                className="flex flex-col items-center gap-4 p-12 rounded-lg border-2 border-dashed border-white/20 cursor-pointer hover:border-white/40 transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-12 h-12 text-white/40" />
                <div className="text-center">
                  <p className="text-white/70 text-lg font-medium">Upload a PDF</p>
                  <p className="text-white/40 text-sm mt-1">Click to select or drag and drop</p>
                </div>
              </div>
            </div>
          ) : (
            <>
              {/* PDF toolbar */}
              <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={currentPage <= 1}
                    className="text-white/70 hover:text-white hover:bg-white/10"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <span className="text-white/70 text-sm min-w-[80px] text-center">
                    {currentPage} / {numPages}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
                    disabled={currentPage >= numPages}
                    className="text-white/70 hover:text-white hover:bg-white/10"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setScale(s => Math.max(0.5, s - 0.2))}
                    className="text-white/70 hover:text-white hover:bg-white/10"
                  >
                    <ZoomOut className="w-4 h-4" />
                  </Button>
                  <span className="text-white/70 text-sm min-w-[50px] text-center">
                    {Math.round(scale * 100)}%
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setScale(s => Math.min(3, s + 0.2))}
                    className="text-white/70 hover:text-white hover:bg-white/10"
                  >
                    <ZoomIn className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    className="text-white/70 hover:text-white hover:bg-white/10 ml-2"
                  >
                    <Upload className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* PDF render area */}
              <div className="flex-1 overflow-auto flex justify-center p-4 pdf-viewer-container">
                <Document
                  file={pdfUrl}
                  onLoadSuccess={onDocumentLoadSuccess}
                  loading={
                    <div className="flex items-center gap-2 text-white/50">
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Loading PDF...
                    </div>
                  }
                >
                  <Page
                    pageNumber={currentPage}
                    scale={scale}
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                    className="pdf-page"
                    customTextRenderer={customTextRenderer}
                  />
                </Document>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Right: Question + Chat */}
      <div className="w-[420px] flex flex-col m-2 ml-1">
        <div className="rounded-sm h-full flex flex-col" style={{ background: "#151515" }}>
          {/* Header */}
          <div className="px-4 py-3 border-b border-white/10">
            <h3 className="text-white font-medium text-sm">Ask about this PDF</h3>
          </div>

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4" style={{ scrollbarWidth: "thin", scrollbarColor: "rgba(255,255,255,0.2) transparent" }}>
            {messages.length === 0 && !currentThinking && !currentResponse && (
              <div className="text-center text-white/40 mt-8">
                <p className="text-sm">Upload a PDF and ask questions about it</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i}>
                {msg.role === "user" && (
                  <div className="flex justify-end pdf-msg-enter-right">
                    <div className="max-w-[85%] rounded-2xl px-4 py-2.5" style={{ background: "#3a3a3a" }}>
                      <p className="text-white text-xs whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                )}
                {msg.role === "thinking" && (
                  <div className="pdf-msg-enter-left">
                    <ThinkingBlock content={msg.content} />
                  </div>
                )}
                {msg.role === "assistant" && (
                  <div className="max-w-[85%] pdf-msg-enter-left">
                    <div className="rounded-2xl px-4 py-2.5" style={{ background: "#2a2a2a" }}>
                      <div className="text-white/90 text-xs leading-relaxed message-content pdf-message">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {/* Live thinking stream */}
            {currentThinking && (
              <div className="max-w-[85%] pdf-msg-enter-left">
                <p className="text-xs text-white/30 mb-1 font-medium flex items-center gap-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Reasoning...
                </p>
                <div
                  className="rounded-lg px-3 py-2 text-white/50 text-xs leading-relaxed overflow-y-auto"
                  style={{ background: "#1a1a1a", maxHeight: "200px" }}
                >
                  {currentThinking}
                </div>
              </div>
            )}

            {/* Live response stream */}
            {currentResponse && (
              <div className="max-w-[85%] pdf-msg-enter-left">
                <div className="rounded-2xl px-4 py-2.5" style={{ background: "#2a2a2a" }}>
                  <div className="text-white/90 text-xs leading-relaxed message-content pdf-message">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {currentResponse}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            )}

            {isLoading && !currentThinking && !currentResponse && (
              <div className="flex items-center gap-2 text-white/40">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span className="text-sm">Analyzing...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="px-4 py-3">
            <div className="flex gap-2 items-end rounded-xl overflow-hidden px-3 py-2" style={{
              background: "rgba(66, 66, 66, 0.7)",
              border: "1px solid rgba(255, 255, 255, 0.1)"
            }}>
              <textarea
                placeholder={pdfFile ? "Ask a question about the PDF..." : "Upload a PDF first"}
                value={inputMessage}
                onChange={(e) => {
                  setInputMessage(e.target.value)
                  e.target.style.height = "auto"
                  e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px"
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    sendQuestion()
                  }
                }}
                disabled={isLoading || !pdfFile}
                rows={1}
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  color: "white",
                  outline: "none",
                  resize: "none",
                  fontSize: "12px",
                  lineHeight: "1.5",
                  padding: "4px 0"
                }}
                className="placeholder:text-gray-500 focus:ring-0 focus:outline-none"
              />
              {isLoading ? (
                <Button
                  onClick={stopGeneration}
                  size="icon"
                  variant="ghost"
                  className="text-white hover:bg-white/10 flex-shrink-0 h-8 w-8"
                >
                  <StopCircle className="w-4 h-4" />
                </Button>
              ) : (
                <Button
                  onClick={sendQuestion}
                  disabled={!inputMessage.trim() || !pdfFile}
                  size="icon"
                  variant="ghost"
                  className="text-white hover:bg-white/10 disabled:opacity-30 flex-shrink-0 h-8 w-8"
                >
                  <Send className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileUpload}
        className="hidden"
      />
    </section>
  )
}
