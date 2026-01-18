import sys
import os
import bisect
import struct
import math 

SIZE_OF_INT = 4

class bptreenode:
    def __init__(self, leaf, b):
        self.is_leaf = leaf
        self.b = b
        self.keys = []
        self.values= [] 
        self.children = [] 
        self.right = None 

    def is_full(self):
        return len(self.keys) >= self.b-1 #max
    
    def byte_to_dat(self): #converts bptreenode to bytes to be written in .dat file
        data = bytearray()
        if self.is_leaf == True:
            data.append(1)
        else:
            data.append(0)
        data+=struct.pack("i", len(self.keys))
        for key in self.keys:
            data+= struct.pack("i",key)
        if self.is_leaf:
            for value in self.values:
                data+= struct.pack("i",value)
            if self.right is not None:
                data+= struct.pack("i",self.right)
            else:
                data+= struct.pack("i",-1)
        else:
            for child in self.children:
                if child is not None:
                    data+=struct.pack("i", child)
                else:
                    data+=struct.pack("i", -1)
            if self.right is not None:
                data+= struct.pack("i",self.right)
            else:
                data+= struct.pack("i",-1)
        return bytes(data)
    
    @staticmethod
    def dat_to_byte(data,b): #converts bytes in .dat file to bptreenode
        is_leaf = data[0] ==1
        offset = 1
        m = struct.unpack("i", data[offset:offset+4])[0]
        offset+=4
        keys = []

        for i in range(m):
            keys.append(struct.unpack("i", data[offset:offset+4])[0])
            offset+=4
        node = bptreenode(is_leaf,b)
        node.keys = keys

        if is_leaf == True:
            values = []
            for i in range(m):
                values.append(struct.unpack("i", data[offset:offset+4])[0])
                offset +=4
            node.values = values
            right_pointer = struct.unpack("i", data[offset:offset+4])[0]
            if right_pointer == -1:
                node.right = None
            else:
                node.right = right_pointer
        else:
            children = []
            for i in range(m+1): #internal nodes
                child_offset = struct.unpack("i", data[offset:offset+4])[0]
                if child_offset == -1:
                    children.append(None)
                else:
                    children.append(child_offset)
                offset+=4

            node.children = children
            right_pointer = struct.unpack("i", data[offset:offset+4])[0]
            if right_pointer == -1:
                node.right = None
            else:
                node.right = right_pointer
        return node

class bptree:
    def __init__(self, filename, b= None, create_new=False):
        self.filename = filename
        self.nodesize = 4096
        if create_new == True:
            self.b = b
            with open(filename, "wb") as f:
                f.write(struct.pack("ii", b, self.nodesize)) #two int val
                f.write(b'\x00'*(self.nodesize-8)) #4088 bytes
                root = bptreenode(True,b)
                f.write(root.byte_to_dat().ljust(self.nodesize,b'\x00'))
            self.root_offset = self.nodesize
        else:
            with open(filename, "rb") as f:
                self.b, self.root_offset = struct.unpack("ii", f.read(8))
            
    def read(self, offset):
        with open(self.filename, "rb") as f:
            f.seek(offset)
            data = f.read(self.nodesize)
            return bptreenode.dat_to_byte(data, self.b)
        
    def write(self, node, offset):
        with open(self.filename, "r+b") as f:
            f.seek(offset)
            f.write(node.byte_to_dat().ljust(self.nodesize,b'\x00')) 
            
    def allocate(self, node):
        with open(self.filename, "ab") as f:
            offset = f.tell()
            f.write(node.byte_to_dat().ljust(self.nodesize, b'\x00'))
        return offset
    
    def search(self, key):
        node, _ = self.search_recursive(self.root_offset, key, print_path=True) 
        if key in node.keys:
            index = node.keys.index(key)
            print(node.values[index])
        else:
            print("NOT FOUND")
   
    def search_recursive(self, offset, key, print_path=False):
        node = self.read(offset)
        if not node.is_leaf and print_path:
            print(",".join(map(str, node.keys)))
        
        if node.is_leaf:
            return node, offset
        child_index = 0 #finding child
        for i, k in enumerate(node.keys):
            if key < k:
                child_index =i
                break
            child_index = i+1
        
        child_offset = node.children[child_index]
        if child_offset is None: #curropted tree
            return node, offset
        return self.search_recursive(node.children[child_index], key, print_path)
   
    def ranged_search(self, start_key, end_key):
        node, _ = self.search_recursive(self.root_offset, start_key) #add 주석
        while node:
            for i, k in enumerate(node.keys):
                if start_key <= k <= end_key:
                    print(f"{k}, {node.values[i]}")
                elif k > end_key:
                    return
            if node.right is None:
                break
            node = self.read(node.right)
    
    def insert(self, key, value):
        root = self.read(self.root_offset)
        result = self.insert_recursive(root, key, value, self.root_offset)
        if result is not None:
            left_node, left_offset, key_up, right_node, right_offset = result
            new_root = bptreenode(False, self.b)
            new_root.keys = [key_up]
            new_root.children = [left_offset,right_offset]
            new_root_offset = self.allocate(new_root)
            self.root_offset = new_root_offset

            with open(self.filename, "r+b") as f:
                f.seek(4)
                f.write(struct.pack("i", new_root_offset))
            self.write(new_root, new_root_offset)
   
    def insert_recursive(self,node,key,value,offset):
        if node.is_leaf:
            if key in node.keys:
                return None #duplicate
            index = bisect.bisect_left(node.keys, key)
            node.keys.insert(index, key)
            node.values.insert(index,value)
            if not node.is_full():
                self.write(node, offset)
                return None
            return self.split_leaf(node,offset)
        else:
            child_index = 0
            for i, k in enumerate(node.keys):
                if key < k:
                    child_index = i
                    break
                child_index = i+1
            child_offset = node.children[child_index]
            child = self.read(child_offset)
            result = self.insert_recursive(child, key, value, child_offset)
            if result is None:
                return None
            
            left, left_offset, key_up, right, right_offset = result

            insert_index = bisect.bisect_left(node.keys, key_up) #new key & child pointer
            node.keys.insert(insert_index, key_up)
            node.children.insert(insert_index+1, right_offset)

            if not node.is_full():
                self.write(node, offset)
                return None
            return self.split_internal(node,offset)
    def split_leaf(self, node, offset):
        middle = len(node.keys)//2
        right_node = bptreenode(True, self.b)
        right_node.keys = node.keys[middle:]
        right_node.values = node.values[middle:]
        right_node.right = node.right

        node.keys = node.keys[:middle]
        node.values = node.values[:middle]

        right_offset = self.allocate(right_node)
        node.right = right_offset
        self.write(node,offset)
        self.write(right_node,right_offset)

        return node, offset, right_node.keys[0], right_node, right_offset

    def split_internal(self, node, offset):
        middle = len(node.keys)//2
        key_up = node.keys[middle]

        right_node = bptreenode(False, self.b)
        right_node.keys = node.keys[middle+1:]
        right_node.children = node.children[middle+1:]

        node.keys = node.keys[:middle]
        node.children = node.children[:middle+1]

        right_offset = self.allocate(right_node)
        self.write(node,offset)
        self.write(right_node,right_offset)

        return node, offset, key_up, right_node, right_offset
   
    def minimum_keys(self):
        return math.ceil((self.b-1)/2) #min number of keys requrired for non-root nodes

    def delete(self,key): #rebalances
        delete = self.delete_recursive(self.root_offset,key, None,-1)    
        
        root = self.read(self.root_offset)
        if not root.is_leaf and len(root.keys) == 0 and len(root.children) > 0:
            self.root_offset = root.children[0] #root is empty
            with open(self.filename, "r+b") as f:
                f.seek(4)
                f.write(struct.pack("i", self.root_offset))
        return delete
    
    def delete_recursive(self, offset, key, parent_offset, child_index):
        node = self.read(offset)
        if node.is_leaf:
            if key not in node.keys:
                return False
            index = node.keys.index(key) #remove key and value
            node.keys.pop(index)
            node.values.pop(index)
            self.write(node, offset)
            
            if parent_offset is not None and len(node.keys) < self.minimum_keys(): #check if need to rebalance
                parent = self.read(parent_offset)
                self.rebalance_leaf(node, offset, parent, parent_offset, child_index)
            return True
        else:
            target_child_index = 0
            for i, k in enumerate(node.keys):
                if key < k:
                    target_child_index = i
                    break
                target_child_index = i+1
            child_offset = node.children[target_child_index]
            delete = self.delete_recursive(child_offset, key, offset, target_child_index)

            if not delete:
                return False
            
            child = self.read(child_offset) #check if need to rebalance
            if not child.is_leaf and len(child.keys) < self.minimum_keys():
                self.rebalance_internal(child, child_offset, node, offset, target_child_index)
            return True
        
    def rebalance_leaf(self, node,offset, parent, parent_offset, child_index):
        minimum_keys = self.minimum_keys()

        if child_index > 0: #left
            left_sibling_offset = parent.children[child_index-1]
            if left_sibling_offset is not None: 
                left_sibling = self.read(left_sibling_offset)
                if len(left_sibling.keys) > minimum_keys: #borrow from left sibling
                    node.keys.insert(0, left_sibling.keys.pop())
                    node.values.insert(0,left_sibling.values.pop())
                    parent.keys[child_index-1] = node.keys[0]
                    self.write(node, offset)
                    self.write(left_sibling, left_sibling_offset)
                    self.write(parent, parent_offset)
                    return
            
        if child_index < len(parent.children)-1: #right
            right_sibling_offset = parent.children[child_index+1]
            if right_sibling_offset is not None:
                right_sibling = self.read(right_sibling_offset)
                if len(right_sibling.keys) >minimum_keys:
                    node.keys.append(right_sibling.keys.pop(0))
                    node.values.append(right_sibling.values.pop(0))
                    parent.keys[child_index] = right_sibling.keys[0]
                    self.write(node, offset)
                    self.write(right_sibling, right_sibling_offset)
                    self.write(parent, parent_offset)
                    return

        #merge
        if child_index >0: #left
            left_sibling_offset = parent.children[child_index-1]
            if left_sibling_offset is not None: 
                left_sibling = self.read(left_sibling_offset)
                self.merge_leaves(left_sibling, left_sibling_offset, node, offset, parent, parent_offset, child_index-1)

        else: #right
            if child_index + 1 < len(parent.children):
                right_sibling_offset = parent.children[child_index+1]
                if right_sibling_offset is not None:
                    right_sibling = self.read(right_sibling_offset)
                    self.merge_leaves(node, offset, right_sibling,right_sibling_offset, parent,parent_offset, child_index)
        
    def rebalance_internal(self, node, offset, parent, parent_offset, child_index):
        minimum_keys = self.minimum_keys()
        
        if child_index > 0: #left
            left_sibling_offset = parent.children[child_index-1]
            if left_sibling_offset is not None: 
                left_sibling = self.read(left_sibling_offset)
                if len(left_sibling.keys) > minimum_keys: #borrow from left sibling
                    separate = parent.keys[child_index-1]
                    node.keys.insert(0, separate)
                    node.children.insert(0, left_sibling.children.pop())
                    parent.keys[child_index-1] = left_sibling.keys.pop()
                    self.write(node, offset)
                    self.write(left_sibling, left_sibling_offset)
                    self.write(parent, parent_offset)
                    return
            
        if child_index < len(parent.children)-1: #right
            right_sibling_offset = parent.children[child_index+1]
            if right_sibling_offset is not None:
                right_sibling = self.read(right_sibling_offset)
                if len(right_sibling.keys) > minimum_keys:
                    separate = parent.keys[child_index]
                    node.keys.append(separate)
                    node.children.append(right_sibling.children.pop(0))
                    parent.keys[child_index] = right_sibling.keys.pop(0)
                    self.write(node, offset)
                    self.write(right_sibling, right_sibling_offset)
                    self.write(parent, parent_offset)
                    return
        
        #merge
        if child_index > 0: #left
            left_sibling_offset = parent.children[child_index-1]
            if left_sibling_offset is not None:    
                left_sibling = self.read(left_sibling_offset)
                self.merge_internal(left_sibling, left_sibling_offset, node, offset, parent, parent_offset, child_index-1)

        else: #right
            if child_index + 1 < len(parent.children):
                right_sibling_offset = parent.children[child_index+1]
                if right_sibling_offset is not None:
                    right_sibling = self.read(right_sibling_offset)
                    self.merge_internal(node, offset, right_sibling,right_sibling_offset, parent,parent_offset, child_index)
    
    def merge_leaves(self, left, left_offset, right, right_offset, parent, parent_offset, separate_index):
        left.keys.extend(right.keys) #merge right->left
        left.values.extend(right.values)
        left.right = right.right

        parent.keys.pop(separate_index) #remove sep & right child from parent
        parent.children.pop(separate_index+1)
        
        self.write(left, left_offset)
        self.write(parent,parent_offset)
        
    def merge_internal(self, left, left_offset, right, right_offset, parent, parent_offset, separate_index):
        separate = parent.keys[separate_index]
        left.keys.append(separate)
        left.keys.extend(right.keys)
        left.children.extend(right.children)

        parent.keys.pop(separate_index) #remove sep & right child from parent
        parent.children.pop(separate_index+1)
        
        self.write(left, left_offset)
        self.write(parent,parent_offset)

   
#main
def main():
    args = sys.argv

    if args[1] == "-c": #create file             -c index_file b
        index_file = args[2] 
        b = int(args[3]) 
        bptree(index_file, b, create_new=True) #overwrite 

    elif args[1] == "-i": #insert                -i index_file data_file
        tree = bptree(args[2])
        with open(args[3], "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    key, value = map(int, line.split(","))
                    tree.insert(key, value)

    elif args[1] == "-d": #delete                -d index_file data_file
        tree = bptree(args[2])
        with open(args[3], "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    key = int(line)
                    tree.delete(key)
    elif args[1] == "-s": #single_key search     -s index_file key
        tree = bptree(args[2])
        key = int(args[3])
        tree.search(key)
    elif args[1] == "-r": #ranged search         -r index_file start_key end_key
        tree = bptree(args[2])
        start_key = int(args[3])
        end_key = int(args[4])
        tree.ranged_search(start_key, end_key)
    else:
        print("unknown command")

if __name__ == "__main__":
    main()
    

