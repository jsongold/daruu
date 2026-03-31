import { useParams, useNavigate } from "react-router-dom"
import { ModeBar } from "../components/ModeBar"
import { PdfViewer } from "../components/PdfViewer"
import { AskQuestionModal } from "../components/AskQuestionModal"
import { ActivityLog } from "../components/InfoChat"
import { LeftPanel } from "../components/LeftPanel"
import { HeaderActions } from "../components/HeaderActions"
import { useFormSession } from "../hooks/useFormSession"
import { useAnnotateMode } from "../hooks/useAnnotateMode"
import { useMapMode } from "../hooks/useMapMode"
import { useRulesMode } from "../hooks/useRulesMode"
import { useFillMode } from "../hooks/useFillMode"
import { usePreviewMode } from "../hooks/usePreviewMode"

export function FormPage() {
  const { conversationId: urlConversationId } = useParams<{ conversationId: string }>()
  const navigate = useNavigate()

  const s = useFormSession(urlConversationId, navigate)

  const { handleLabelClick, handleFieldClick, handleDeleteAnnotation } = useAnnotateMode({
    mode: s.mode,
    selectedLabelId: s.selectedLabelId,
    formId: s.formId,
    textBlocks: s.textBlocks,
    setAnnotations: s.setAnnotations,
    setSelectedLabelId: s.setSelectedLabelId,
    setSelectedFieldId: s.setSelectedFieldId,
    setIsLoading: s.setIsLoading,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const { handleRunMap } = useMapMode({
    formId: s.formId,
    conversationId: s.conversationId,
    setFieldLabelMaps: s.setFieldLabelMaps,
    setIsMapping: s.setIsMapping,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const { handleUnderstand, handleSaveRules } = useRulesMode({
    conversationId: s.conversationId,
    setRulesItems: s.setRulesItems,
    setMode: s.setMode,
    setIsUnderstanding: s.setIsUnderstanding,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  const { handleFill, handleAskReply, handleModalSubmit, handleModalClose } = useFillMode({
    conversationId: s.conversationId,
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
    conversationId: s.conversationId,
    setIsAsking: s.setIsAsking,
    setMode: s.setMode,
    setPendingQuestions: s.setPendingQuestions,
    setAskHistory: s.setAskHistory,
    setError: s.setError,
    chatWindow: s.chatWindow,
  })

  // handleSaveRules and handleAskReply retained for future use
  void handleSaveRules
  void handleAskReply

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-3">
          <h1 className="font-bold text-gray-800 text-sm">daru-pdf</h1>
          {s.formId && (
            <span className="text-xs text-gray-400 font-mono truncate max-w-[160px]">{s.formId}</span>
          )}
        </div>

        <ModeBar mode={s.mode} onChange={s.handleModeChange} disabled={!s.formId} />

        <HeaderActions
          formId={s.formId}
          conversationId={s.conversationId}
          isLoading={s.isLoading}
          isFilling={s.isFilling}
          isAsking={s.isAsking}
          isMapping={s.isMapping}
          isUnderstanding={s.isUnderstanding}
          error={s.error}
          onUnderstand={handleUnderstand}
          onMap={handleRunMap}
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
        <LeftPanel
          mode={s.mode}
          fields={s.fields}
          annotations={s.annotations}
          fieldLabelMaps={s.fieldLabelMaps}
          selectedLabelId={s.selectedLabelId}
          selectedFieldId={s.selectedFieldId}
          currentPage={s.currentPage}
          formId={s.formId}
          onValueChange={s.handleValueChange}
          onDeleteAnnotation={handleDeleteAnnotation}
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
          <ActivityLog
            entries={s.activityLog}
            onSend={handleSendInfo}
            disabled={!s.conversationId || s.isFilling}
          />
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
