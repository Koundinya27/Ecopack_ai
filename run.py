from ecopack_app import create_app, DevConfig

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
