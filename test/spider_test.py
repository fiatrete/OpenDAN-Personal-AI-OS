

def test_main():
    sm = service_manager()
    
    knownlege_base_service =  sm.get('knowlege_base')
    knownlege_base_service.start()

    email_spider = sm.get('email_spider')
    email_spider.start()

    doc_embeding_service = sm.get('doc_embeding_service')
    doc_embeding_service.start()

    ia = agents_manager().get("ai_info_assistor")
    chat_session = ia.get_default_chat_session("master");
    chat_session.chat("Who responded to my issue last week");
    chat_session.wait_response();
    #print(chat_session.last_msg());
    
if __name__ == '__main__':
    test_main()
    