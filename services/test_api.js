const axios = require('axios');

const FASTAPI_URL = "http://127.0.0.1:8000";

async function test() {
  try {
    const res = await axios.post(`${FASTAPI_URL}/predict`, {
      image_path: "C:\\Users\\SUMIT\\MVC_BV_LH\\2026_04_17_10_23_09_2000\\img0054_10_23_11_532_532665.jpg"
    });

    console.log("✅ API Response:", res.data);

  } catch (err) {
    console.error("❌ Error:", err.message);
  }
}

test();
