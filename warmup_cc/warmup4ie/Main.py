from warmup4ie import Warmup4IE

if __name__ == '__main__':
    warmup = Warmup4IE('user@example.com', 'REDACTED_PASSWORD')
    print(warmup.get_all_devices())
    device = warmup.get_device_by_name("Studio")
    a = "{:02}:{:02}".format(3, 5)
    print(a)
    warmup.set_override("39481", 24, 17, 30)
    print("{}".format(device))

