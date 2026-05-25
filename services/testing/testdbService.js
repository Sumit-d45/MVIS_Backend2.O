const {
  checkTrainExists,
  waitForTrainProcessed,
  getAxleTimeline
} = require('../db_service'); // adjust path if needed

(async () => {
  try {
    const trainId = "2026_04_17_10_23_09_2000"; // 👈 use actual trainId from your folder

    console.log("\n🚀 START TEST\n");

    // 1️⃣ Check Train Exists
    const exists = await checkTrainExists(trainId);

    if (!exists) {
      console.log("❌ Train NOT found in DB");
      return;
    }

    // 2️⃣ Wait for IsProcessed
    const ready = await waitForTrainProcessed(trainId);

    if (!ready) {
      console.log("❌ Train not ready (IsProcessed != 1)");
      return;
    }

    // 3️⃣ Fetch Timeline
    const timeline = await getAxleTimeline(trainId);

    console.log("\n📦 FINAL TIMELINE:");
    console.log(timeline);

  } catch (err) {
    console.error("❌ ERROR:", err.message);
  }
})();
