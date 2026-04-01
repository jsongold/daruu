import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { FormPage } from "./pages/FormPage"
import { AdminPage } from "./pages/AdminPage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/form" element={<FormPage />} />
        <Route path="/form/c/:conversationId" element={<FormPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/form" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
