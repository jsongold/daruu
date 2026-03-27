import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { FormPage } from "./pages/FormPage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/form" element={<FormPage />} />
        <Route path="/form/c/:sessionId" element={<FormPage />} />
        <Route path="*" element={<Navigate to="/form" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
