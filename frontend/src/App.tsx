/**
 * 应用路由配置
 */
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import Dashboard from '@/pages/Dashboard'
import Run from '@/pages/Run'
import Chapters from '@/pages/Chapters'
import ChapterDetail from '@/pages/ChapterDetail'
import Canon from '@/pages/Canon'
import Staging from '@/pages/Staging'
import Stats from '@/pages/Stats'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="run" element={<Run />} />
          <Route path="chapters" element={<Chapters />} />
          <Route path="chapters/:id" element={<ChapterDetail />} />
          <Route path="canon" element={<Canon />} />
          <Route path="staging" element={<Staging />} />
          <Route path="stats" element={<Stats />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
