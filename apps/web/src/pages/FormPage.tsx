import { useParams, useNavigate } from "react-router-dom"
import { ModeBar } from "../components/ModeBar"
import { PdfViewer } from "../components/PdfViewer"
import { AnnotatePanel } from "../components/AnnotatePanel"
import { EditPanel } from "../components/EditPanel"
import { AskPanel } from "../components/AskPanel"
import { AskQuestionModal } from "../components/AskQuestionModal"
import { MapPanel } from "../components/MapPanel"
import { ActivityLog } from "../components/InfoChat"
import { RulesPanel } from "../components/RulesPanel"
import { FieldSidebar } from "../components/FieldSidebar"
import { HeaderActions } from "../components/HeaderActions"
import { useFormSession } from "../hooks/useFormSession"
import { useAnnotateMode } from "../hooks/useAnnotateMode"
import { useMapMode } from "../hooks/useMapMode"
import { useRulesMode } from "../hooks/useRulesMode"
import { useFillMode } from "../hooks/useFillMode"
import { usePreviewMode } from "../hooks/usePreviewMode"
import type { Mode } from "../api/formClient"

export function FormPage() {
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const s = useFormSession(urlSessionId, navigate)

  const { handleLabelClick, handleFieldClick, handleDeleteAnnotation } = useAnnotateMode({
    mode: s.mode,
    selectedLabelId: s.selectedLabelId,
    documentId: s.documentId,
    textBlocks: s.textBlocks,
    setAnnotations: s.setAnnotations,
    setSelectedLabelId: s.setSelectedLabelId,
    setSelectedFieldId: s.setSelectedFieldId,
    setIsLoading: s.setIsLoading,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const { handleRunMap } = useMapMode({
    documentId: s.documentId,
    setFieldLabelMaps: s.setFieldLabelMaps,
    setIsMapping: s.setIsMapping,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const { handleUnderstand, handleSaveRules } = useRulesMode({
    sessionId: s.sessionId,
    setRulesItems: s.setRulesItems,
    setMode: s.setMode,
    setIsUnderstanding: s.setIsUnderstanding,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const { handleFill, handleAskReply, handleModalSubmit, handleModalClose } = useFillMode({
    sessionId: s.sessionId,
    fields: s.fields,
    pendingQuestions: s.pendingQuestions,
    setFields: s.setFields,
    setMode: s.setMode,
    setIsFilling: s.setIsFilling,
    setAskHistory: s.setAskHistory,
    setPendingQuestions: s.setPendingQuestions,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const { handleSendInfo, handleAsk } = usePreviewMode({
    sessionId: s.sessionId,
    setIsAsking: s.setIsAsking,
    setMode: s.setMode,
    setPendingQuestions: s.setPendingQuestions,
    setAskHistory: s.setAskHistory,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const rightPanel: Record<Mode, React.ReactNode> = {
    preview: (
      <ActivityLog entries={s.activityLog} onSend={handleSendInfo} disabled={!s.sessionId || s.isFilling} />
    ),
    edit: <EditPanel fields={s.fields} onValueChange={s.handleValueChange} />,
    annotate: (
      <AnnotatePanel
        annotations={s.annotations}
        selectedLabelId={s.selectedLabelId}
        selectedFieldId={s.selectedFieldId}
        onDelete={handleDeleteAnnotation}
      />
    ),
    map: (
      <MapPanel maps={s.fieldLabelMaps} onRunMap={handleRunMap} isLoading={s.isMapping} disabled={!s.documentId} />
    ),
    fill: (
      <AskPanel history={s.askHistory} onReply={handleAskReply} mode={s.mode} isLoading={s.isFilling || s.isAsking} />
    ),
    ask: (
      <AskPanel history={s.askHistory} onReply={handleAskReply} mode={s.mode} isLoading={s.isFilling || s.isAsking} />
    ),
    rules: (
      <RulesPanel rules={s.rulesItems} isLoading={s.isUnderstanding} onSave={handleSaveRules} />
    ),
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-3">
          <h1 className="font-bold text-gray-800 text-sm">daru-pdf</h1>
          {s.documentId && (
            <span className="text-xs text-gray-400 font-mono truncate max-w-[160px]">{s.documentId}</span>
          )}
        </div>

        <ModeBar mode={s.mode} onChange={s.handleModeChange} disabled={!s.documentId} />

        <HeaderActions
          documentId={s.documentId}
          sessionId={s.sessionId}
          isLoading={s.isLoading}
          isFilling={s.isFilling}
          isAsking={s.isAsking}
          isUnderstanding={s.isUnderstanding}
          error={s.error}
          onUnderstand={handleUnderstand}
          onAsk={handleAsk}
          onFill={() => handleFill()}
          onUploadClick={() => s.fileInputRef.current?.click()}
        />
        <input
          ref={s.fileInputRef}
          type="file"
          accept=".pdf"
          onChange={s.handleFileInput}
          className="hidden"
        />
      </header>

      <div className="flex flex-1 overflow-hidden">
        <FieldSidebar
          fields={s.fields}
          annotations={s.annotations}
          fieldLabelMaps={s.fieldLabelMaps}
          currentPage={s.currentPage}
          documentId={s.documentId}
        />

        <main
          className={[
            "flex-1 overflow-hidden",
            s.isDragging ? "bg-blue-50 border-2 border-dashed border-blue-400" : "",
          ].join(" ")}
          onDragOver={(e) => { e.preventDefault(); s.setIsDragging(true) }}
          onDragLeave={() => s.setIsDragging(false)}
          onDrop={s.handleDrop}
        >
          <PdfViewer
            imageUrl={s.pageImageUrl}
            fields={s.fields}
            textBlocks={s.textBlocks}
            mode={s.mode}
            selectedLabelId={s.selectedLabelId}
            selectedFieldId={s.selectedFieldId}
            onLabelClick={handleLabelClick}
            onFieldClick={handleFieldClick}
            page={s.currentPage}
            totalPages={s.totalPages}
            onPageChange={s.setCurrentPage}
            excludedPages={s.excludedPages}
            onToggleIncludePage={s.handleToggleIncludePage}
          />
        </main>

        <aside className="w-64 bg-white border-l border-gray-200 overflow-hidden flex flex-col shrink-0">
          {rightPanel[s.mode]}
        </aside>
      </div>

      {s.pendingQuestions.length > 0 && (
        <AskQuestionModal
          questions={s.pendingQuestions}
          onSubmit={handleModalSubmit}
          onClose={handleModalClose}
        />
      )}
    </div>
  )
}
