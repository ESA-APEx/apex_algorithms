from flask import Flask, request, jsonify
from generate import generate_process  # import from your original logic

app = Flask(__name__)

# create the process only once
process = generate_process()

@app.route("/flood", methods=["POST"])
def flood_endpoint():
    try:
        data = request.get_json()

        # use the function from generate.py
        result = process["apply"](data)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)