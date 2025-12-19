<!DOCTYPE html>
<html>
<head>
    <title>Security Automation Portal</title>
</head>
<body>

<h2>Security Automation Portal</h2>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    <div style="background:#198754;color:white;padding:10px;margin-bottom:10px">
      {% for msg in messages %}
        {{ msg }}<br>
      {% endfor %}
    </div>
  {% endif %}
{% endwith %}

<form action="/upload" method="POST" enctype="multipart/form-data">
    <input type="file" name="file" required>
    <button type="submit">Upload</button>
</form>

<hr>

<button onclick="location.href='/run/vul/devops'">
    Run Vulnerability DevOps
</button>

<div id="status" style="margin-top:15px;font-weight:bold;"></div>

<hr>

<a href="/downloads/vul_devops">View Vulnerability Outputs</a><br><br>

<a href="/logout">Logout</a>

<script>
function pollStatus() {
    fetch("/status/vul/devops")
        .then(res => res.json())
        .then(data => {
            const el = document.getElementById("status");
            if (data.status === "RUNNING") {
                el.innerHTML = "⏳ Vulnerability DevOps is processing…";
            } else if (data.status === "COMPLETED") {
                el.innerHTML = "✅ Vulnerability DevOps completed";
            }
        });
}
setInterval(pollStatus, 5000);
</script>

</body>
</html>
