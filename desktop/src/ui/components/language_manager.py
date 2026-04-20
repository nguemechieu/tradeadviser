

# class LanguageManager:
#     def __init__(self, app):
#         self.app = app
#         self.translator = QTranslator()

#     def switch_language(self, qm_file):
#         self.app.removeTranslator(self.translator)
#         self.translator.load(qm_file)
#         self.app.installTranslator(self.translator)

#         # Force refresh
#         for w in self.app.allWidgets():
#             w.update()
