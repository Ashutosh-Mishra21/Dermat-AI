import { useEffect } from "react";
import "./App.css";

function App() {
  useEffect(() => {
    // Redirect to the static DermaSense AI website
    window.location.replace("/dermasense/index.html");
  }, []);

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "DM Sans, system-ui, sans-serif",
      background: "#F8F6F1",
      color: "#1C2B2D",
    }}>
      <p>Loading DermaSense AI…</p>
    </div>
  );
}

export default App;
